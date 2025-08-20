import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import datetime, os, qrcode
from pyzbar.pyzbar import decode
from PIL import Image

# ----------------- Firebase Init -----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.title("🎓 Student Attendance via QR Pass")

menu = st.sidebar.radio("Menu", ["Generate Pass", "Upload QR for Attendance", "Attendance Report"])

# ----------------- Generate Pass -----------------
if menu == "Generate Pass":
    st.subheader("🎟 Generate Student Pass")

    sid = st.text_input("Student ID")
    name = st.text_input("Student Name")
    course = st.text_input("Course")

    if st.button("Generate Pass"):
        if sid and name:
            # Save student
            db.collection("students").document(sid).set({
                "name": name,
                "course": course
            })

            # Create QR
            qr = qrcode.make(sid)
            qr.save(f"{sid}.png")

            # Generate PDF pass
            filename = f"Pass_{sid}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=letter)
            table_data = [["Student Pass"], [f"ID: {sid}"], [f"Name: {name}"], [f"Course: {course}"]]
            table = Table(table_data, colWidths=[400])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.grey),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 14),
                ("BOX", (0,0), (-1,-1), 1, colors.black),
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ]))
            doc.build([table])

            st.success("✅ Pass generated successfully")
            with open(filename, "rb") as file:
                st.download_button("⬇️ Download Pass PDF", file, file_name=filename)

            os.remove(filename)
        else:
            st.error("⚠️ Fill all fields")

# ----------------- Upload QR for Attendance -----------------
elif menu == "Upload QR for Attendance":
    st.subheader("📸 Upload QR Code to Mark Attendance")
    qr_file = st.file_uploader("Upload Student QR", type=["png", "jpg", "jpeg"])

    if qr_file:
        img = Image.open(qr_file)
        decoded = decode(img)
        if decoded:
            sid = decoded[0].data.decode("utf-8")
            student = db.collection("students").document(sid).get()
            if student.exists:
                data = student.to_dict()
                db.collection("attendance").document(f"{sid}_{datetime.date.today()}").set({
                    "student_id": sid,
                    "name": data["name"],
                    "course": data["course"],
                    "date": str(datetime.date.today()),
                    "status": "Present"
                })
                st.success(f"✅ Attendance marked for {data['name']} ({sid})")
            else:
                st.error("❌ Student not found in database")
        else:
            st.error("⚠️ Could not read QR code")

# ----------------- Attendance Report -----------------
elif menu == "Attendance Report":
    st.subheader("📄 Generate Attendance Report")
    date = st.date_input("Select Date", datetime.date.today())
    if st.button("Generate Report"):
        records = db.collection("attendance").where("date", "==", str(date)).stream()
        data = [["Student ID", "Name", "Course", "Date", "Status"]]
        for rec in records:
            r = rec.to_dict()
            data.append([r["student_id"], r["name"], r["course"], r["date"], r["status"]])

        if len(data) > 1:
            filename = f"Attendance_{date}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=letter)
            table = Table(data)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.grey),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
            ]))
            doc.build([table])
            st.success(f"✅ Report generated: {filename}")
            with open(filename, "rb") as file:
                st.download_button("⬇️ Download PDF", file, file_name=filename)
            os.remove(filename)
        else:
            st.warning("⚠️ No attendance records for this date")
