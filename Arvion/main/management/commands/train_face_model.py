import os
import cv2
import pickle
import numpy as np
import mediapipe as mp
from sklearn.neighbors import KNeighborsClassifier
from django.core.management.base import BaseCommand
from django.conf import settings
from main.models import CustomUser  

mp_face_mesh = mp.solutions.face_mesh
def extract_embedding(image):
    """Դեմքի 468 կետերի կոորդինատները վերադարձնող ֆունկցիա"""
    with mp_face_mesh.FaceMesh(
        static_image_mode=True, max_num_faces=1, min_detection_confidence=0.5
    ) as face_mesh:
        results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        if not results.multi_face_landmarks:
            return None
        landmarks = results.multi_face_landmarks[0].landmark
        return np.array([(lm.x, lm.y, lm.z) for lm in landmarks]).flatten()


class Command(BaseCommand):
    help = "Trains the face recognition model using patient profile pictures from the database."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Starting face recognition model training...")
        )

        patients_with_pics = CustomUser.objects.filter(
            patient_profile__isnull=False, profile_picture__isnull=False
        ).exclude(profile_picture="")

        if not patients_with_pics.exists():
            self.stdout.write(
                self.style.WARNING("No patients with profile pictures found. Exiting.")
            )
            return

        embeddings = []
        labels = []

        for user in patients_with_pics:
            image_path = os.path.join(settings.MEDIA_ROOT, user.profile_picture.name)
            if not os.path.exists(image_path):
                self.stdout.write(
                    self.style.ERROR(
                        f"Image not found for user {user.username}: {image_path}"
                    )
                )
                continue
            try:
                with open(image_path, "rb") as f:
                    file_bytes = np.frombuffer(f.read(), dtype=np.uint8)

                image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error decoding image for user {user.username}: {e}"
                    )
                )
                image = None

            if image is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"Could not read or decode image for user {user.username} at path: {image_path}"
                    )
                )
                continue

            embedding = extract_embedding(image)

            if embedding is not None:
                embeddings.append(embedding)
                labels.append(user.id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully processed face for user: {user.username} (ID: {user.id})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Could not detect face for user: {user.username}"
                    )
                )

        if not embeddings:
            self.stdout.write(
                self.style.ERROR(
                    "No faces were detected in any of the images. Model not created."
                )
            )
            return

        knn_clf = KNeighborsClassifier(
            n_neighbors=1, algorithm="ball_tree", weights="distance"
        )
        knn_clf.fit(embeddings, labels)

        model_dir = os.path.join(settings.BASE_DIR, "face_models")
        os.makedirs(model_dir, exist_ok=True)

        with open(os.path.join(model_dir, "face_classifier.pkl"), "wb") as f:
            pickle.dump(knn_clf, f)

        with open(os.path.join(model_dir, "face_embeddings.pkl"), "wb") as f:
            pickle.dump(embeddings, f)

        with open(os.path.join(model_dir, "face_labels.pkl"), "wb") as f:
            pickle.dump(labels, f)

        self.stdout.write(
            self.style.SUCCESS(
                f"Model training complete! {len(labels)} faces processed. Models saved in {model_dir}"
            )
        )
