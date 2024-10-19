from flask import Flask, Response, render_template, request
import cv2
import mediapipe as mp
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin
cred = credentials.Certificate("mockup-3b1d2-firebase-adminsdk-g9so1-9db8709364.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

# Only include shoulder, elbow, hip, and knee joints
JOINTS = {
    'left_shoulder': 11,
    'right_shoulder': 12,
    'left_elbow': 13,
    'right_elbow': 14,
    'left_hip': 23,
    'right_hip': 24,
    'left_knee': 25,
    'right_knee': 26
}


# Function to calculate the angle between three points
def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)

    if angle > 180.0:
        angle = 360 - angle

    return angle

def extract_joint_angles(landmarks):
    joint_angles = {}

    for joint_name, joint_index in JOINTS.items():
        if joint_name.endswith('elbow'):
            shoulder = landmarks[JOINTS['left_shoulder'] if 'left' in joint_name else JOINTS['right_shoulder']]
            elbow = landmarks[joint_index]
            # Wrist removed, now calculating angles just with shoulder and elbow
            joint_angles[joint_name] = calculate_angle([shoulder.x, shoulder.y], [elbow.x, elbow.y], [elbow.x, elbow.y])
        elif joint_name.endswith('shoulder'):
            hip = landmarks[JOINTS['left_hip'] if 'left' in joint_name else JOINTS['right_hip']]
            shoulder = landmarks[joint_index]
            elbow = landmarks[JOINTS['left_elbow'] if 'left' in joint_name else JOINTS['right_elbow']]
            joint_angles[joint_name] = calculate_angle([hip.x, hip.y], [shoulder.x, shoulder.y], [elbow.x, elbow.y])
        elif joint_name.endswith('hip'):
            shoulder = landmarks[JOINTS['left_shoulder'] if 'left' in joint_name else JOINTS['right_shoulder']]
            hip = landmarks[joint_index]
            knee = landmarks[JOINTS['left_knee'] if 'left' in joint_name else JOINTS['right_knee']]
            joint_angles[joint_name] = calculate_angle([shoulder.x, shoulder.y], [hip.x, hip.y], [knee.x, knee.y])
        elif joint_name.endswith('knee'):
            hip = landmarks[JOINTS['left_hip'] if 'left' in joint_name else JOINTS['right_hip']]
            knee = landmarks[joint_index]
            # Ankle removed, now calculating angles just with hip and knee
            joint_angles[joint_name] = calculate_angle([hip.x, hip.y], [knee.x, knee.y], [knee.x, knee.y])

    return joint_angles


# Function to get reference pose joint angles from Firestore
def get_reference_pose_from_firestore(exercise_name):
    doc_ref = db.collection('joint_angle').document(exercise_name)
    doc = doc_ref.get()

    if doc.exists:
        reference_pose = doc.to_dict()
        reference_pose.pop('name', None)  # Remove non-joint fields
        return reference_pose
    else:
        print(f"Document '{exercise_name}' not found in Firestore")
        return {}
    
# Function to resize frame
def resize_frame(frame, target_width):
    height, width = frame.shape[:2]
    aspect_ratio = width / height
    new_height = int(target_width / aspect_ratio)
    return cv2.resize(frame, (target_width, new_height))

# Function to generate live video frames
# Function to generate live video frames
def generate_frames(exercise_name):
    cap = cv2.VideoCapture(0)  # Open webcam feed

    # Load reference joint angles from Firestore for the specific exercise
    reference_pose = get_reference_pose_from_firestore(exercise_name)

    threshold = 20  # Set the threshold for angle matching

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while True:
            success, frame = cap.read()

            if not success:
                break

            frame = cv2.flip(frame, 1)  # Flip the frame horizontally

            frame = resize_frame(frame, 1280)  # Resize frame

            # Convert the frame to RGB
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)

            total_joints = 0  
            matching_joints = 0  

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Extract joint angles for the live video
                live_joint_angles = extract_joint_angles(landmarks)

                # Compare live joint angles with reference angles
                for joint, live_angle in live_joint_angles.items():
                    if joint in reference_pose:
                        ref_angle = reference_pose[joint]
                        angle_diff = abs(ref_angle - live_angle)

                        if angle_diff <= threshold:
                            matching_joints += 1  

                        total_joints += 1  

                matching_percentage = (matching_joints / total_joints) * 100 if total_joints > 0 else 0

                if matching_percentage >= 60:
                    cv2.putText(frame, 'CORRECT POSTURE', (int(frame.shape[1] / 2) - 150, frame.shape[0] - 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3, cv2.LINE_AA)

                # Draw pose landmarks on the frame
                mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # Encode the frame to JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            # Yield the frame to be served
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')



@app.route('/video_feed')
def video_feed():
    # Retrieve the 'exercise_name' from the query parameters
    exercise_name = request.args.get('exercise_name', default='default_exercise')
    return Response(generate_frames(exercise_name), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/sign_up')
def sign_up_page():
    return render_template('register.html')

@app.route('/home')
def home_page():
    return render_template('homepage.html')

@app.route('/general')
def general_page():
    return render_template('general-exercise.html')

@app.route('/physio')
def physio_page():
    return render_template('physio.html')

@app.route('/pose1-cam')
def pose1_cam_page():
    return render_template('pose1-cam.html')

@app.route('/pose2-cam')
def pose2_cam_page():
    return render_template('pose2-cam.html')

@app.route('/pose3-cam')
def pose3_cam_page():
    return render_template('pose3-cam.html')

@app.route('/pose4-cam')
def pose4_cam_page():
    return render_template('pose4-cam.html')

@app.route('/pose1-physio')
def pose1_physio_page():
    return render_template('pose1-physio.html')

@app.route('/pose2-physio')
def pose2_physio_page():
    return render_template('pose2-physio.html')

@app.route('/pose3-physio')
def pose3_physio_page():
    return render_template('pose3-physio.html')

@app.route('/pose4-physio')
def pose4_physio_page():
    return render_template('pose4-physio.html')

if __name__ == "__main__":
    app.run(debug=True)
