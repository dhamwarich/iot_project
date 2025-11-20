import cv2
import mediapipe as mp

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

# Initialize webcam
cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 480)

# Hand tracking model
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

def classify_gesture(landmarks):
    """Classify gesture based on finger positions."""
    tips = [4, 8, 12, 16, 20]
    fingers = []

    # Thumb (check x-axis direction)
    if landmarks[tips[0]].x < landmarks[tips[0] - 1].x:
        fingers.append(1)
    else:
        fingers.append(0)

    # Other four fingers (check y-axis direction)
    for i in range(1, 5):
        if landmarks[tips[i]].y < landmarks[tips[i] - 2].y:
            fingers.append(1)
        else:
            fingers.append(0)

    total = fingers.count(1)

    # Gesture mapping
    if total == 0:
        return "fist"
    elif total == 1:
        return "one"
    elif total == 5:
        return "open"
    else:
        return "none"

while True:
    success, img = cap.read()
    if not success:
        break

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)

    gesture = "none"
    action = "stop"

    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(img, handLms, mp_hands.HAND_CONNECTIONS)
            gesture = classify_gesture(handLms.landmark)

    # Map gestures to actions
    if gesture == "fist":
        action = "forward"
    elif gesture == "one":
        action = "spin"
    else:
        action = "stop"

    # Print and display
    print(action)
    cv2.putText(img, f"Action: {action}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Gesture Control", img)

    # Exit with 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
