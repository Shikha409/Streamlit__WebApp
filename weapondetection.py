import streamlit as st
from PIL import Image
import cv2
import numpy as np
from ultralytics import YOLO
import os
import tempfile
import time

# Load the YOLOv8 model
@st.cache_resource
def load_model():
    return YOLO("weights/best.pt")

model = load_model()

# Streamlit app
st.title("YOLOv8 Objects Detection App")

# Sidebar for options
st.sidebar.title("Detection Options Config")
option = st.sidebar.radio("1. Select Input Type:", ("Upload Image", "Upload Video", "Livecam Detection"))

# Sidebar settings
MAX_BOXES_TO_DRAW = st.sidebar.number_input('2. Maximum Boxes To Draw', value=5, min_value=1, max_value=20)
DEVICES = st.sidebar.selectbox("3. Select Device", ['cpu', '0', '1', '2'], index=0)
MIN_SCORE_THRES = st.sidebar.slider('4. Min Confidence Score Threshold', min_value=0.0, max_value=1.0, value=0.4)
save_option = st.sidebar.selectbox("5. Save Result?", ("Yes", "No"))

# Set the model to use the selected device
model.to(DEVICES)

# Function to process image
def process_image(image):
    results = model(image, conf=MIN_SCORE_THRES, max_det=MAX_BOXES_TO_DRAW)
    return results[0]

# Function to process video frame
def process_video_frame(frame):
    results = model(frame, conf=MIN_SCORE_THRES, max_det=MAX_BOXES_TO_DRAW)
    return results[0]

# Function to display detection results
def display_results(result, original_image):
    col1, col2 = st.columns(2)
    with col1:
        st.write("Original Image")
        st.image(original_image, use_column_width=True)
    with col2:
        st.write("Detected Objects")
        st.image(result.plot(), use_column_width=True)
    
    speed_info = result.speed
    st.write(f"Image Details: {original_image.size[1]}x{original_image.size[0]}")
    st.write(f"Objects Detected: {len(result.boxes)}")
    st.write(f"Classes: {', '.join([model.names[int(cls)] for cls in result.boxes.cls])}")
    st.write(f"Speed: {speed_info['preprocess']:.1f}ms preprocess, {speed_info['inference']:.1f}ms inference, {speed_info['postprocess']:.1f}ms postprocess")

# Image upload processing
if option == "Upload Image":
    uploaded_image = st.file_uploader("Choose an image...", type=("jpg", "jpeg", "png", 'bmp', 'webp'))
    if uploaded_image is not None:
        image = Image.open(uploaded_image)
        result = process_image(image)
        display_results(result, image)
        
        if save_option == "Yes":
            result_image = result.plot()
            st.sidebar.image(result_image, caption="Detected Image", use_column_width=True)
            st.sidebar.download_button("Download Result Image", cv2.imencode('.jpg', result_image)[1].tobytes(), "result_image.jpg")

# Video upload processing
elif option == "Upload Video":
    uploaded_video = st.file_uploader("Upload a video...", type=["mp4", "avi", "mov"])
    if uploaded_video is not None:
        tfile = tempfile.NamedTemporaryFile(delete=False) 
        tfile.write(uploaded_video.read())
        
        st.video(tfile.name)
        
        cap = cv2.VideoCapture(tfile.name)
        
        # Create a placeholder for snapshots
        snapshot_placeholder = st.empty()
        
        # Create columns for snapshot controls
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            snapshot_button = st.button("Take Snapshot")
        with col2:
            auto_snapshot = st.checkbox("Auto Snapshot")
        with col3:
            snapshot_interval = st.number_input("Snapshot Interval (seconds)", min_value=1, value=5)
        
        last_snapshot_time = time.time()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            result = process_video_frame(frame)
            processed_frame = result.plot()
            
            current_time = time.time()
            if snapshot_button or (auto_snapshot and current_time - last_snapshot_time >= snapshot_interval):
                snapshot_placeholder.image(processed_frame, channels="BGR", caption="Latest Snapshot", use_column_width=True)
                last_snapshot_time = current_time
                snapshot_button = False  # Reset the button state
            
            # Display frame info
            st.write(f"Frame: {cap.get(cv2.CAP_PROP_POS_FRAMES):.0f}, "
                     f"Objects: {len(result.boxes)}, "
                     f"Classes: {', '.join([model.names[int(cls)] for cls in result.boxes.cls])}")
        
        cap.release()
        os.unlink(tfile.name)

# Set the model to use the selected device
model.to(DEVICES)



if option == "Webcam Detection":
    start_button = st.button("Start Webcam Detection")
    # Main options for camera detection modes
      #option = st.selectbox("Select Mode", ["Choose...", "Webcam Detection", "IP Camera Detection"])

    if start_button:
        cap = cv2.VideoCapture(0)
        processed_frames = []

        # Create a placeholder for the video
        video_placeholder = st.empty()

        st.selectbox("Select Mode", ["Choose...", "Webcam Detection", "IP Camera Detection"])
        st.subheader("Detection Frame Detail Results")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                st.warning("Failed to read from the webcam. Check if it's connected.")
                break

            # Perform object detection on the frame
            results = model(frame, conf=MIN_SCORE_THRES, max_det=MAX_BOXES_TO_DRAW)
            processed_frame = results[0].plot()
            processed_frames.append(processed_frame)

            # Extract speed information
            speed_info = results[0].speed if isinstance(results[0].speed, dict) else {'inference': 0, 'preprocess': 0, 'postprocess': 0}
            inference_time = speed_info.get('inference', 0)
            preprocess_time = speed_info.get('preprocess', 0)
            postprocess_time = speed_info.get('postprocess', 0)

            # Extract detections and their labels
            detections = results[0].boxes
            detection_text = []
            for box in detections[:MAX_BOXES_TO_DRAW]:
                class_id = int(box.cls)
                label = model.names[class_id]
                detection_text.append(label)

            detection_count = len(detection_text)
            detection_text_str = ', '.join(detection_text) if detection_text else "No detections"

            # Update the placeholder with the processed frame
            video_placeholder.image(processed_frame[:, :, ::-1], channels="RGB", caption="Webcam Detection")

            # Display frame processing info 
            st.write(f"Frame {len(processed_frames) - 1}: {frame.shape[0]}x{frame.shape[1]}, "
                     f"(Objects: {detection_count}, {detection_text_str}), "
                     f"Speed: {preprocess_time:.1f}ms preprocess, {inference_time:.1f}ms inference, {postprocess_time:.1f}ms postprocess")

        cap.release()

        # Save the processed webcam video if the user chooses to do so
        save_option = st.sidebar.radio("Save Processed Video?", ("No", "Yes"))
        if save_option == "Yes" and processed_frames:
            result_video_path = st.text_input("Enter the filename to save the video (e.g., 'result.mp4')", "result.mp4")
            out = cv2.VideoWriter(result_video_path, cv2.VideoWriter_fourcc(*'mp4v'), 20, (processed_frames[0].shape[1], processed_frames[0].shape[0]))
            for frame in processed_frames:
                out.write(frame)
            out.release()
            st.success(f"Video saved as {result_video_path}")

elif option == "IP Camera Detection":
    start_button = st.button("Start IP Camera Detection")

    if start_button:
        ip_url = st.text_input("Enter IP Camera URL (e.g., rtsp:// or http://)", "")
        
        if ip_url:
            cap = cv2.VideoCapture(ip_url)
            processed_frames = []

            # Create a placeholder for the video
            video_placeholder = st.empty()

            st.subheader("Detection Frame Detail Results")

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    st.warning("Failed to read from the IP Camera. Check if the URL is correct.")
                    break

                # Perform object detection on the frame
                results = model(frame, conf=MIN_SCORE_THRES, max_det=MAX_BOXES_TO_DRAW)
                processed_frame = results[0].plot()
                processed_frames.append(processed_frame)

                # Extract speed information
                speed_info = results[0].speed if isinstance(results[0].speed, dict) else {'inference': 0, 'preprocess': 0, 'postprocess': 0}
                inference_time = speed_info.get('inference', 0)
                preprocess_time = speed_info.get('preprocess', 0)
                postprocess_time = speed_info.get('postprocess', 0)

                # Extract detections and their labels
                detections = results[0].boxes
                detection_text = []
                for box in detections[:MAX_BOXES_TO_DRAW]:
                    class_id = int(box.cls)
                    label = model.names[class_id]
                    detection_text.append(label)

                detection_count = len(detection_text)
                detection_text_str = ', '.join(detection_text) if detection_text else "No detections"

                # Update the placeholder with the processed frame
                video_placeholder.image(processed_frame[:, :, ::-1], channels="RGB", caption="IP Camera Detection")

                # Display frame processing info 
                st.write(f"Frame {len(processed_frames) - 1}: {frame.shape[0]}x{frame.shape[1]}, "
                         f"(Objects: {detection_count}, {detection_text_str}), "
                         f"Speed: {preprocess_time:.1f}ms preprocess, {inference_time:.1f}ms inference, {postprocess_time:.1f}ms postprocess")

            cap.release()

            # Save the processed video if the user chooses to do so
            save_option = st.sidebar.radio("Save Processed Video?", ("No", "Yes"))
            if save_option == "Yes" and processed_frames:
                result_video_path = st.text_input("Enter the filename to save the video (e.g., 'result.mp4')", "result.mp4")
                out = cv2.VideoWriter(result_video_path, cv2.VideoWriter_fourcc(*'mp4v'), 20, (processed_frames[0].shape[1], processed_frames[0].shape[0]))
                for frame in processed_frames:
                    out.write(frame)
                out.release()
                st.success(f"Video saved as {result_video_path}")

else:
    st.write("Select 'Webcam Detection' or 'IP Camera Detection' to start.")
