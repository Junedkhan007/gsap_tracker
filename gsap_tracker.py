# app.py
import streamlit as st  # type: ignore
import paramiko
import io
import pandas as pd
from datetime import datetime

# -------------------------------
# Page Config (adds logo & title in browser tab)
# -------------------------------
st.set_page_config(
    page_title="PSA File Extractor",
    page_icon="📂",
    layout="wide",
)

# -------------------------------
# Banner
# -------------------------------
st.markdown(
    """
    <style>
        .main-title {
            text-align: center;
            color: #4CAF50; /* Blue */
            text-decoration: underline;
        }
        .sub-title {
            text-align: center;
            color: white; /* White */
        }
        .developer {
            text-align: center;
            font-family: 'Courier New', monospace;
            font-style: italic;
            font-size: 14px; /* Smaller */
            color: #333333;
        }
    </style>

    <h2 class="main-title">DELTEK REPLICON PSA FILE EXTRACTOR</h2>
    <h3 class="sub-title">GSAP TRACKER</h3>
    <h4 class="developer">Developed by Juned Khan</h4>
    <hr>
    """,
    unsafe_allow_html=True,
)


# -------------------------------
# Sidebar - User Input
# -------------------------------
st.sidebar.markdown('<p class="sidebar-title">📌 Report Options</p>', unsafe_allow_html=True)
target_date = st.sidebar.date_input("Select a Date")
target_date_str = target_date.strftime("%Y-%m-%d")

# -------------------------------
# Fetch SFTP credentials from Streamlit secrets
# -------------------------------
host = st.secrets["sftp_host"]
port = st.secrets["sftp_port"]
username = st.secrets["sftp_username"]
password = st.secrets["sftp_password"]

input_dir = "/Production/Inbound/Resource Assignments/Archive"
log_dir   = "/Production/Inbound/Resource Assignments/Logs/Archive"

# -------------------------------
# Run Button
# -------------------------------
if st.sidebar.button("🚀 Generate Report"):
    st.info("🔄 Connecting to SFTP and processing files... Please wait!")

    try:
        # Connect to SFTP
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Step 1: Get Input Files (PGP)
        input_files = {}
        for f in sftp.listdir_attr(input_dir):
            if f.filename.endswith(".pgp"):
                file_date = datetime.fromtimestamp(f.st_mtime).strftime("%Y-%m-%d")
                if file_date == target_date_str:
                    input_files[f.filename] = f.st_mtime

        # Step 2: Get Log Files + Calculate processing time
        report = []
        for f in sftp.listdir_attr(log_dir):
            if f.filename.endswith(".csv"):
                file_date = datetime.fromtimestamp(f.st_mtime).strftime("%Y-%m-%d")
                if file_date == target_date_str:
                    file_path = f"{log_dir}/{f.filename}"
                    size = f.st_size

                    # Count rows
                    with sftp.file(file_path, "r") as remote_file:
                        content = io.TextIOWrapper(remote_file, encoding="utf-8")
                        row_count = sum(1 for _ in content) - 1

                    # Match log with input file
                    base_id = f.filename.split("_")[1]
                    input_file = next((k for k in input_files if k.startswith(base_id)), None)

                    processing_time = ""
                    if input_file:
                        input_time = datetime.fromtimestamp(input_files[input_file])
                        log_time = datetime.fromtimestamp(f.st_mtime)
                        diff = log_time - input_time

                        total_seconds = int(diff.total_seconds())
                        days, remainder = divmod(total_seconds, 86400)
                        hours, remainder = divmod(remainder, 3600)
                        minutes, seconds = divmod(remainder, 60)

                        if days > 0:
                            processing_time = f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
                        else:
                            processing_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    report.append(
                        {
                            "File Name": f.filename,
                            "Record Count": row_count,
                            "File Size (Bytes)": size,
                            "Processing Time": processing_time,
                        }
                    )

        sftp.close()
        transport.close()

        if report:
            st.success("✅ Report generated successfully!")

            df = pd.DataFrame(report)
            st.dataframe(df, use_container_width=True, height=400)

            # CSV export
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Report as CSV",
                data=csv,
                file_name=f"report_{target_date_str}.csv",
                mime="text/csv",
            )
        else:
            st.warning("⚠️ No matching files found for the selected date.")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
