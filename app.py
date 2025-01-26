from flask import Flask, render_template, request, redirect, url_for, flash
import cv2
from deepface import DeepFace
import os
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Ensure 'faces' directory exists
os.makedirs('faces', exist_ok=True)

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",        # Replace with your MySQL username
        password="1234",     # Replace with your MySQL password
        database="student_attendance"
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['id']
        student_name = request.form['name']

        # Check if student is already registered
        try:
            conn = get_db_connection()
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
                existing_student = cursor.fetchone()
            
            if existing_student:
                flash("Student already registered. Please proceed to login.")
                return redirect(url_for('login'))

            # Capture image for new registration
            cam = cv2.VideoCapture(0)
            if not cam.isOpened():
                flash("Failed to access the camera. Please try again.")
                return redirect(url_for('register'))

            captured = False
            while True:
                ret, frame = cam.read()
                if not ret:
                    flash("Failed to capture image. Please try again.")
                    break
                cv2.imshow("Press 'q' to capture your image", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    image_path = f'faces/{student_id}.jpg'
                    cv2.imwrite(image_path, frame)
                    captured = True
                    break

            cam.release()
            cv2.destroyAllWindows()

            if captured:
                # Save student info in the database
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO students (id, name, image_path) VALUES (%s, %s, %s)",
                        (student_id, student_name, image_path)
                    )
                    conn.commit()
                flash("Registration successful! Please login.")
                return redirect(url_for('login'))

        except mysql.connector.Error as err:
            flash(f"Database Error: {err}")
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['id']
        student_name = request.form['name']

        # Fetch the student's registered image path from the database
        try:
            conn = get_db_connection()
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM students WHERE id = %s AND name = %s", (student_id, student_name))
                student = cursor.fetchone()

            if not student:
                flash("Student ID or name does not match our records.")
                return redirect(url_for('login'))

            # Start face capture and verification
            cam = cv2.VideoCapture(0)
            if not cam.isOpened():
                flash("Failed to access the camera. Please try again.")
                return redirect(url_for('login'))

            captured = False
            while True:
                ret, frame = cam.read()
                if not ret:
                    flash("Failed to capture image. Please try again.")
                    break
                cv2.imshow("Press 'q' to capture your image", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    captured_image_path = 'faces/temp.jpg'
                    cv2.imwrite(captured_image_path, frame)
                    captured = True
                    break

            cam.release()
            cv2.destroyAllWindows()

            if captured:
                threshold = 0.4
                try:
                    # Verify the captured face image with the registered image
                    result = DeepFace.verify(
                        img1_path=captured_image_path,
                        img2_path=student['image_path'],
                        enforce_detection=False
                    )

                    if result['distance'] < threshold:
                        with conn.cursor() as cursor:
                            timestamp = datetime.now()
                            cursor.execute(
                                "INSERT INTO attendance (student_id, student_name, attendance_time) VALUES (%s, %s, %s)",
                                (student['id'], student['name'], timestamp)
                            )
                            conn.commit()
                        flash(f"Attendance marked for {student['name']} at {timestamp}")
                    else:
                        flash("Face does not match the registered ID and name. Attendance not marked.")

                except Exception as e:
                    flash(f"Verification error: {str(e)}")

                finally:
                    if os.path.exists(captured_image_path):
                        os.remove(captured_image_path)

        except mysql.connector.Error as err:
            flash(f"Database Error: {err}")
        finally:
            conn.close()

    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=False)