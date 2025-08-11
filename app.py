# digital_carbon_footprint_with_gsheets.py
import streamlit as st
import pandas as pd
from datetime import datetime

# Google Sheets libs
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Digital Carbon Footprint Calculator", layout="wide")

# -------------------------
# Google Sheets config
# -------------------------
CREDS_FILE = "credentials.json"
SHEET_NAME = "Dati CFC"

GSCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gsheet_client():
    """Return an authorized gspread client or raise an exception."""
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, GSCOPE)
    client = gspread.authorize(creds)
    return client

def ensure_sheet_and_headers():
    """
    Ensure the spreadsheet exists and the header row is present.
    Returns the first worksheet (sheet1).
    """
    client = get_gsheet_client()
    try:
        sh = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = client.create(SHEET_NAME)
    sheet = sh.sheet1

    required_headers = ["timestamp", "Total Emissions", "Devices Emissions", "Digital Activities Emissions", "AI Tools Emissions"]
    headers = sheet.row_values(1)
    # If header row is missing or not matching required set, replace it
    if not headers or set(required_headers) != set(headers):
        try:
            if headers:
                sheet.delete_row(1)
        except Exception:
            pass
        sheet.insert_row(required_headers, index=1)
    return sheet

def append_results_to_gsheet(total, devices, activities, ai_tools):
    """Append a single row with timestamp and emissions to the sheet."""
    sheet = ensure_sheet_and_headers()
    ts = datetime.utcnow().isoformat()
    row = [ts, float(total), float(devices), float(activities), float(ai_tools)]
    sheet.append_row(row, value_input_option="USER_ENTERED")

def load_gsheet_df():
    """Return a pandas DataFrame of the sheet contents (excluding header)."""
    sheet = ensure_sheet_and_headers()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # ensure numeric columns
    for col in ["Total Emissions", "Devices Emissions", "Digital Activities Emissions", "AI Tools Emissions"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def compute_medians_from_sheet():
    """Return medians dict or None if the sheet is empty / unreadable."""
    df = load_gsheet_df()
    if df.empty:
        return None
    med = {
        "Total Emissions": float(df["Total Emissions"].median()) if "Total Emissions" in df.columns else None,
        "Devices Emissions": float(df["Devices Emissions"].median()) if "Devices Emissions" in df.columns else None,
        "Digital Activities Emissions": float(df["Digital Activities Emissions"].median()) if "Digital Activities Emissions" in df.columns else None,
        "AI Tools Emissions": float(df["AI Tools Emissions"].median()) if "AI Tools Emissions" in df.columns else None,
    }
    return med

# -------------------------
# App state + factors
# -------------------------
if "page" not in st.session_state or st.session_state.page not in ["intro", "main", "results"]:
    st.session_state.page = "intro"
if "role" not in st.session_state:
    st.session_state.role = ""
if "device_inputs" not in st.session_state:
    st.session_state.device_inputs = {}
if "device_list" not in st.session_state:
    st.session_state.device_list = []
if "results" not in st.session_state:
    st.session_state.results = {}

activity_factors = {
    "Student": {
        "MS Office (e.g. Excel, Word, PPT…)": 0.00901,
        "Technical softwares (e.g. Matlab, Python…)": 0.00901,
        "Web browsing": 0.0264,
        "Watching lecture recordings": 0.0439,
        "Online classes streaming or video call": 0.112,
        "Reading study materials on your computer (e.g. slides, articles, digital textbooks)": 0.00901
    },
    "Professor": {
        "MS Office (e.g. Excel, Word, PPT…)": 0.00901,
        "Web browsing": 0.0264,
        "Videocall (e.g. Zoom, Teams…)": 0.112,
        "Online classes streaming": 0.112,
        "Reading materials on your computer (e.g. slides, articles, digital textbooks)": 0.00901,
        "Technical softwares (e.g. Matlab, Python…)": 0.00901
    },
    "Staff Member": {
        "MS Office (e.g. Excel, Word, PPT…)": 0.00901,
        "Management software (e.g. SAP)": 0.00901,
        "Web browsing": 0.0264,
        "Videocall (e.g. Zoom, Teams…)": 0.112,
        "Reading materials on your computer (e.g. documents)": 0.00901
    }
}

ai_factors = {
    "Summarize texts or articles": 0.000711936,
    "Translate sentences or texts": 0.000363008,
    "Explain a concept": 0.000310784,
    "Generate quizzes or questions": 0.000539136,
    "Write formal emails or messages": 0.000107776,
    "Correct grammar or style": 0.000107776,
    "Analyze long PDF documents": 0.001412608,
    "Write or test code": 0.002337024,
    "Generate images": 0.00206,
    "Brainstorm for thesis or projects": 0.000310784,
    "Explain code step-by-step": 0.003542528,
    "Prepare lessons or presentations": 0.000539136
}

device_ef = {
    "Desktop Computer": 296,
    "Laptop Computer": 170,
    "Smartphone": 38.4,
    "Tablet": 87.1,
    "External Monitor": 235,
    "Headphones": 12.17,
    "Printer": 62.3,
    "Router/Modem": 106
}

eol_modifier = {
    "I bring it to a certified e-waste collection center": -0.0384,
    "I throw it away in general waste": 0.0595,
    "I return it to manufacturer for recycling or reuse": -0.3461,
    "I sell or donate it to someone else": -0.6991,
    "I store it at home, unused": 0.0113
}

DAYS = 250  # Typical number of work/study days per year

# -------------------------
# Pages
# -------------------------
def show_intro():
    st.title("Welcome to the Digital Carbon Footprint Calculator")
    st.write(
        "This app estimates your digital carbon footprint based on your devices, digital activities, and AI tool usage."
    )
    role = st.selectbox("Please select your role:", ["Student", "Professor", "Staff Member"])
    st.session_state.role = role
    if st.button("Start"):
        st.session_state.page = "main"
        st.experimental_rerun()

def show_main():
    st.title("☁️ Digital Usage Form")

    # === DEVICES ===
    st.header("💻 Devices")
    st.markdown("""
    Choose the digital devices you currently use, and for each one, provide a few details about how you use it and what you do when it's no longer needed.

    - **Years of use**: Estimate how many years you've used (or plan to use) the device in total.
    - **Condition**:
      - *New*: You were the first owner of the device when it was purchased.
      - *Used*: The device was previously owned or refurbished when you started using it.
    - **Ownership**:
      - *Personal*: You’re the only one who regularly uses the device.
      - *Shared*: The device is used by other people in your household or team.
    - **End-of-life behavior**: What do you usually do with your devices when you stop using them? (e.g. recycle, donate, store in a drawer...)
    """)

    # Device list management
    device_to_add = st.selectbox("Select a device to add:", list(device_ef.keys()))
    if st.button("➕ Add Device"):
        count = sum(d.startswith(device_to_add) for d in st.session_state.device_list)
        new_id = f"{device_to_add}_{count}"
        st.session_state.device_list.append(new_id)
        st.session_state.device_inputs[new_id] = {
            "years": 1.0,
            "used": "New",
            "shared": "Personal",
            "eol": "I bring it to a certified e-waste collection center"
        }
        st.success(f"✅ '{device_to_add}' has been added successfully!")

    if st.session_state.device_list:
        st.info(f"Added devices ({len(st.session_state.device_list)}):")
        for dev_key in st.session_state.device_list:
            device_name = dev_key.rsplit("_", 1)[0]
            st.markdown(f"---\n**{device_name}**")
            c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
            with c1:
                years = st.number_input(
                    label="Years of use",
                    min_value=0.1,
                    max_value=10.0,
                    value=st.session_state.device_inputs[dev_key]["years"],
                    key=f"years_{dev_key}",
                    step=0.1,
                    format="%.1f"
                )
            with c2:
                used = st.selectbox(
                    label="Condition",
                    options=["New", "Used"],
                    index=0 if st.session_state.device_inputs[dev_key]["used"] == "New" else 1,
                    key=f"used_{dev_key}"
                )
            with c3:
                shared = st.selectbox(
                    label="Ownership",
                    options=["Personal", "Shared"],
                    index=0 if st.session_state.device_inputs[dev_key]["shared"] == "Personal" else 1,
                    key=f"shared_{dev_key}"
                )
            with c4:
                eol = st.selectbox(
                    label="End-of-life behavior",
                    options=list(eol_modifier.keys()),
                    index=list(eol_modifier.keys()).index(st.session_state.device_inputs[dev_key]["eol"]),
                    key=f"eol_{dev_key}"
                )
            # Update session state for this device
            st.session_state.device_inputs[dev_key]["years"] = years
            st.session_state.device_inputs[dev_key]["used"] = used
            st.session_state.device_inputs[dev_key]["shared"] = shared
            st.session_state.device_inputs[dev_key]["eol"] = eol

        # Button to clear all devices
        if st.button("🗑️ Remove all devices"):
            st.session_state.device_list = []
            st.session_state.device_inputs = {}

    else:
        st.info("No devices added yet. Please add at least one device.")

    # === DIGITAL ACTIVITIES ===
    st.header("📱 Digital Activities")

    role = st.session_state.role
    if role in activity_factors:
        act_factors = activity_factors[role]
        st.write(f"Select how many hours you typically spend on each digital activity **per day**.")
        st.write(f"Typical academic year is {DAYS} days (e.g. 250).")

        activity_hours = {}
        for activity in act_factors:
            h = st.number_input(
                label=f"{activity} (hours/day)",
                min_value=0.0,
                max_value=24.0,
                value=0.0,
                step=0.25,
                key=f"activity_{activity}"
            )
            activity_hours[activity] = h
    else:
        st.warning("Please select a valid role on the previous page.")
        activity_hours = {}

    # === AI TOOLS ===
    st.header("🤖 AI Tools Usage")

    st.write("Select which AI-related tasks you perform and how many times per day you perform each task.")

    ai_counts = {}
    for task in ai_factors:
        cnt = st.number_input(
            label=f"{task} (times/day)",
            min_value=0,
            max_value=1000,
            value=0,
            step=1,
            key=f"ai_{task}"
        )
        ai_counts[task] = cnt

    # Calculate footprint button
    if st.button("Calculate Carbon Footprint"):
        # 1) Calculate Devices emissions per device
        device_emissions_total = 0
        for dev_key in st.session_state.device_list:
            device_name = dev_key.rsplit("_", 1)[0]
            info = st.session_state.device_inputs.get(dev_key, {})
            years = float(info.get("years", 1))
            used = info.get("used", "New")
            shared = info.get("shared", "Personal")
            eol = info.get("eol", "I bring it to a certified e-waste collection center")

            ef = device_ef.get(device_name, 0)
            years_modifier = 1 if used == "New" else 0.7
            shared_modifier = 1 if shared == "Personal" else 0.5
            eol_mod = eol_modifier.get(eol, 0)

            dev_emission = (ef * years_modifier * years * shared_modifier) + eol_mod
            device_emissions_total += dev_emission

        # 2) Calculate Digital Activities emissions
        digital_activities_emissions = 0
        for act, h in activity_hours.items():
            factor = activity_factors.get(role, {}).get(act, 0)
            # Multiply by hours per day * DAYS per year * factor
            digital_activities_emissions += h * DAYS * factor

        # 3) Calculate AI tools emissions
        ai_emissions = 0
        for task, cnt in ai_counts.items():
            factor = ai_factors.get(task, 0)
            ai_emissions += cnt * factor * DAYS  # count times/day * factor * days/year

        total_emissions = device_emissions_total + digital_activities_emissions + ai_emissions

        st.session_state.results = {
            "Total Emissions": total_emissions,
            "Devices Emissions": device_emissions_total,
            "Digital Activities Emissions": digital_activities_emissions,
            "AI Tools Emissions": ai_emissions
        }

        # Append to Google Sheets
        try:
            append_results_to_gsheet(
                total_emissions,
                device_emissions_total,
                digital_activities_emissions,
                ai_emissions
            )
            st.success("Your data has been saved successfully!")
        except Exception as e:
            st.error(f"Failed to save data to Google Sheets: {e}")

        st.session_state.page = "results"
        st.experimental_rerun()

def show_results():
    st.title("📊 Your Digital Carbon Footprint Results")

    results = st.session_state.results
    if not results:
        st.warning("No results found. Please fill in your data first.")
        if st.button("Go back to input form"):
            st.session_state.page = "main"
            st.experimental_rerun()
        return

    total = results["Total Emissions"]
    devices = results["Devices Emissions"]
    activities = results["Digital Activities Emissions"]
    ai_tools = results["AI Tools Emissions"]

    st.metric(label="Total Emissions (kg CO₂ eq/year)", value=f"{total:.2f}")
    st.metric(label="Devices Emissions (kg CO₂ eq/year)", value=f"{devices:.2f}")
    st.metric(label="Digital Activities Emissions (kg CO₂ eq/year)", value=f"{activities:.2f}")
    st.metric(label="AI Tools Emissions (kg CO₂ eq/year)", value=f"{ai_tools:.2f}")

    # Show comparison with median from Google Sheets data
    medians = compute_medians_from_sheet()
    if medians:
        st.write("---")
        st.subheader("Comparison with other users (Median values)")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Median Total Emissions", f"{medians['Total Emissions']:.2f}")
            st.metric("Median Devices Emissions", f"{medians['Devices Emissions']:.2f}")
        with col2:
            st.metric("Median Digital Activities Emissions", f"{medians['Digital Activities Emissions']:.2f}")
            st.metric("Median AI Tools Emissions", f"{medians['AI Tools Emissions']:.2f}")

    else:
        st.info("No other users' data available for comparison yet.")

    if st.button("Calculate Again"):
        st.session_state.page = "main"
        st.experimental_rerun()

# -------------------------
# Main routing
# -------------------------
def main():
    if st.session_state.page == "intro":
        show_intro()
    elif st.session_state.page == "main":
        show_main()
    elif st.session_state.page == "results":
        show_results()

if __name__ == "__main__":
    main()
