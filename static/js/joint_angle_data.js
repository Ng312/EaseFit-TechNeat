
// Function to fetch joint angles from a JSON file and upload to Firebase Firestore
async function saveJointAnglesFromJson(jsonPath) {
  try {
    // Fetch JSON data containing joint angles
    const response = await fetch(jsonPath);
    const posturesData = await response.json(); // Parse the JSON data

    // Loop through each posture and save to Firestore
    for (const [postureName, jointAngles] of Object.entries(posturesData)) {
      // Create or update the document with the posture name as the key in Firestore
      const docRef = await db
        .collection("pose_references")
        .doc(postureName)
        .set(jointAngles);
      console.log(
        `Joint angles for ${postureName} successfully written to Firestore!`
      );
    }
  } catch (error) {
    console.error("Error writing joint angles to Firestore: ", error);
  }
}

// Call the function with the path to the JSON file
saveJointAnglesFromJson("/static/data/joint_angle.json");
