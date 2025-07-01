import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeRegressor, plot_tree
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, r2_score
import matplotlib.pyplot as plt

# Load the dataset
data = pd.read_csv('student_readiness_dataset.csv')

# Prepare the data
# Convert categorical variables to numerical using Label Encoding
le_gender = LabelEncoder()
le_education = LabelEncoder()
le_paud = LabelEncoder()

data['gender_encoded'] = le_gender.fit_transform(data['gender'])
data['father_education_encoded'] = le_education.fit_transform(data['father_education'])
data['mother_education_encoded'] = le_education.fit_transform(data['mother_education'])
data['paud_experience_encoded'] = le_paud.fit_transform(data['paud_experience'])

# Prepare features (X) and target variable (y)
X = data[['age', 'gender_encoded', 'father_education_encoded', 'mother_education_encoded', 'paud_experience_encoded']]
y = data['readiness_score']

# Split the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Create and train the Decision Tree model
dt_model = DecisionTreeRegressor(max_depth=5, random_state=42)
dt_model.fit(X_train, y_train)

# Make predictions
y_pred = dt_model.predict(X_test)

# Calculate performance metrics
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("\nModel Performance Metrics:")
print(f"Mean Squared Error: {mse:.2f}")
print(f"R-squared Score: {r2:.2f}")

# Visualize the Decision Tree
plt.figure(figsize=(20,10))
plot_tree(dt_model, feature_names=['Age', 'Gender', 'Father Education', 'Mother Education', 'PAUD Experience'], 
          filled=True, rounded=True)
plt.savefig('decision_tree_visualization.png')

# Feature importance
feature_importance = pd.DataFrame({
    'Feature': ['Age', 'Gender', 'Father Education', 'Mother Education', 'PAUD Experience'],
    'Importance': dt_model.feature_importances_
})
print("\nFeature Importance:")
print(feature_importance.sort_values(by='Importance', ascending=False))

# Save the encoders and model information
import joblib
joblib.dump(le_gender, 'le_gender.joblib')
joblib.dump(le_education, 'le_education.joblib')
joblib.dump(le_paud, 'le_paud.joblib')
joblib.dump(dt_model, 'decision_tree_model.joblib')

# Example predictions
print("\nExample Predictions:")
example_data = X_test[:5]
example_predictions = dt_model.predict(example_data)
for i in range(5):
    print(f"Actual Score: {y_test.iloc[i]:.2f}, Predicted Score: {example_predictions[i]:.2f}")
