import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import datetime, os, qrcode, cv2, numpy as np
from pyzbar.pyzbar import decode

# ----------------- Firebase Init -----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ----------------- Streamlit UI -----------------
st.set_page_config(page_title="Student Attendance System", layout="wide")
st.title("🎓 Student Attendance Tracker with Passes")

menu = st.sidebar.radio("📌 Menu", ["Add Student", "Generate Student Pass", "Mark Attendance", "Generate Report"])

# ----------------- Add Student -----------------
if menu == "Add Student":
    st.subheader("➕ Register New Student")

    with st.form("student_form"):
        student_id = st.text_input("Student ID")
        name = st.text_input("Full Name")
        course = st.text_input("Course/Department")
        submit = st.form_submit_button("Add Student")

        if submit:
            if student_id and name:
                db.collection("students").document(student_id).set({
                    "name": name,
                    "course": course,
                })
                st.success(f"✅ Student {name} ({student_id}) added successfully!")
            else:
                st.error("⚠️ Please fill all required fields.")

# ----------------- Generate Student Pass -----------------
elif menu == "Generate Student Pass":
    st.subheader("🎫 Generate Pass for Student")

    students = db.collection("students").stream()
    student_list = {s.id: s.to_dict()["name"] for s in students}

    if student_list:
        selected_id = st.selectbox("Select Student", list(student_list.keys()))
        generate_pass = st.button("Generate Pass")

        if generate_pass:
            student_data = db.collection("students").document(selected_id).get().to_dict()
            name, course = student_data["name"], student_data.get("course", "")

            # Generate QR Code
            qr = qrcode.make(selected_id)
            qr_file = f"{selected_id}_qr.png"
            qr.save(qr_file)

            # Create PDF Pass
            pdf_file = f"pass_{selected_id}.pdf"
            doc = SimpleDocTemplate(pdf_file, pagesize=letter)
            styles = getSampleStyleSheet()

            data = [
                [Paragraph("<b>🎓 Student Pass</b>", styles["Title"])],
                [f"Name: {name}"],
                [f"ID: {selected_id}"],
                [f"Course: {course}"],
                ["Scan QR to mark attendance"],
                [Image(qr_file, width=120, height=120)]
            ]

            table = Table(data, colWidths=300)
            table.setStyle(TableStyle([
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("TEXTCOLOR", (0,0), (-1,0), colors.darkblue),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ]))

            doc.build([table])
            os.remove(qr_file)

            st.success("✅ Pass generated successfully!")
            with open(pdf_file, "rb") as f:
                st.download_button("⬇️ Download Pass", f, file_name=pdf_file)

            os.remove(pdf_file)
    else:
        st.warning("⚠️ No students found. Please add students first.")

# ----------------- Mark Attendance -----------------
elif menu == "Mark Attendance":
    st.subheader("📝 Mark Attendance")

    option = st.radio("Choose Method", ["Manual", "Scan Pass (QR)"])

    if option == "Manual":
        students = db.collection("students").stream()
        for student in students:
            data = student.to_dict()
            sid = student.id
            status = st.radio(
                f"{sid} - {data['name']} ({data.get('course','')})",
                ["Present", "Absent"],
                key=f"att_{sid}_{datetime.date.today()}"
            )
            # Save attendance
            db.collection("attendance").document(f"{sid}_{datetime.date.today()}").set({
                "student_id": sid,
                "name": data['name'],
                "course": data.get('course', ''),
                "date": str(datetime.date.today()),
                "status": status
            })

    else:  # QR Scan
        qr_file = st.file_uploader("Upload Student Pass (QR Image)", type=["png", "jpg", "jpeg"])
        if qr_file:
            file_bytes = np.asarray(bytearray(qr_file.read()), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, 1)
            st.image(img, channels="BGR")

            decoded = decode(img)
            if decoded:
                sid = decoded[0].data.decode("utf-8")
                student_ref = db.collection("students").document(sid).get()
                if student_ref.exists:
                    student = student_ref.to_dict()
                    db.collection("attendance").document(f"{sid}_{datetime.date.today()}").set({
                        "student_id": sid,
                        "name": student["name"],
                        "course": student.get("course", ""),
                        "date": str(datetime.date.today()),
                        "status": "Present"
                    })
                    st.success(f"✅ Attendance marked for {student['name']} ({sid})")
                else:
                    st.error("❌ Student not found in database!")
            else:
                st.warning("⚠️ No QR code detected in the uploaded image.")

# ----------------- Generate Report -----------------
elif menu == "Generate Report":
    st.subheader("📄 Generate Attendance Report (PDF)")

    date = st.date_input("Select Date", datetime.date.today())
    generate = st.button("Generate Report")

    if generate:
        records = db.collection("attendance").where("date", "==", str(date)).stream()
        data = [["Student ID", "Name", "Course", "Date", "Status"]]

        for rec in records:
            r = rec.to_dict()
            data.append([r['student_id'], r['name'], r['course'], r['date'], r['status']])

        if len(data) == 1:
            st.warning("⚠️ No records found for this date.")
        else:
            filename = f"Attendance_{date}.pdf"
            doc = SimpleDocTemplate(filename, pagesize=letter)
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
            ]))
            doc.build([table])

            st.success(f"✅ Report generated: {filename}")
            with open(filename, "rb") as file:
                st.download_button("⬇️ Download PDF", file, file_name=filename)

            os.remove(filename)
