from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from functools import wraps
import pandas as pd
import pickle
from sklearn.tree import DecisionTreeRegressor
from sklearn.preprocessing import LabelEncoder
import csv
from datetime import datetime
import os
import secrets
import joblib
import numpy as np

# Initialize Flask app
app = Flask(__name__)
# Generate secure secret key or use environment variable
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Login credentials - should be moved to environment variables in production
VALID_USERNAME = os.environ.get('ADMIN_USERNAME') or "admin"
VALID_PASSWORD = os.environ.get('ADMIN_PASSWORD') or "12345678"

# Load trained model and encoders
try:
    dt_model = joblib.load('decision_tree_model.joblib')
    le_gender = joblib.load('le_gender.joblib')
    le_education = joblib.load('le_education.joblib')
    le_paud = joblib.load('le_paud.joblib')
    model_loaded = True
    print("Machine learning model loaded successfully")
except FileNotFoundError:
    print("Warning: Model files not found. Training new model...")
    model_loaded = False
    dt_model = None
    le_gender = None
    le_education = None
    le_paud = None

# Define available options
gender_classes = ['L', 'P']
education_levels = ['Tidak Sekolah', 'SD', 'SMP', 'SMA', 'D3', 'S1', 'S2']
age_ranges = [5.0, 5.5, 6.0, 6.5, 7.0]
paud_options = ['Ya', 'Tidak']

# Store predictions (max 30 per day)
daily_predictions = {}

def get_daily_predictions():
    today = datetime.now().strftime("%Y%m%d")
    if today not in daily_predictions:
        daily_predictions[today] = []
    return daily_predictions[today]

def add_prediction(prediction_data):
    predictions = get_daily_predictions()
    if len(predictions) >= 30:
        predictions.pop(0)  # Remove oldest prediction if limit reached
    predictions.append(prediction_data)

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('predictor'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/predictor')
@login_required
def predictor():
    return render_template('index.html', 
                         education_levels=education_levels,
                         genders=gender_classes,
                         age_ranges=age_ranges,
                         paud_options=paud_options)

@app.route('/earning')
@login_required
def earning():
    return render_template('earning.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        # Get values from the form
        name = request.form['name']
        age = float(request.form['age'])
        gender = request.form['gender']
        father_education = request.form['father_education']
        mother_education = request.form['mother_education']
        paud_experience = request.form['paud_experience']

        # Use machine learning model if available
        if model_loaded and dt_model is not None:
            try:
                # Encode categorical variables using trained encoders
                gender_encoded = le_gender.transform([gender])[0]
                father_education_encoded = le_education.transform([father_education])[0]
                mother_education_encoded = le_education.transform([mother_education])[0]
                paud_experience_encoded = le_paud.transform([paud_experience])[0]
                
                # Create feature array for prediction
                features = np.array([[age, gender_encoded, father_education_encoded, 
                                   mother_education_encoded, paud_experience_encoded]])
                
                # Make prediction using the trained model
                final_prediction = dt_model.predict(features)[0]
                final_prediction = max(0, min(100, final_prediction))  # Ensure prediction is within valid range
                
                # Determine readiness level based on prediction score
                if final_prediction >= 85:
                    readiness_level = "Siap"
                elif final_prediction >= 75:
                    readiness_level = "Cukup Siap"
                else:
                    readiness_level = "Belum Siap"
                    
            except ValueError as e:
                # Handle cases where encoding fails (unknown categories)
                print(f"Encoding error: {e}")
                # Fall back to rule-based prediction
                final_prediction, readiness_level = fallback_prediction(age, gender, father_education, mother_education, paud_experience)
        else:
            # Use fallback prediction if model not loaded
            final_prediction, readiness_level = fallback_prediction(age, gender, father_education, mother_education, paud_experience)

        # Store prediction data
        prediction_record = {
            'name': name,
            'age': f"{age} tahun",
            'gender': gender,
            'father_education': father_education,
            'mother_education': mother_education,
            'paud_experience': paud_experience,
            'prediction': round(final_prediction, 2),
            'readiness_level': readiness_level,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        add_prediction(prediction_record)

        return jsonify({
            'success': True,
            'prediction': round(final_prediction, 2),
            'readiness_level': readiness_level
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def fallback_prediction(age, gender, father_education, mother_education, paud_experience):
    """Fallback prediction logic when ML model is not available"""
    readiness_level = "Belum Siap"
    final_prediction = 65.0

    # Define education level groups
    basic_education = ['SD', 'SMP']
    higher_education = ['SMA', 'D3', 'S1', 'S2']
    s1_s2_education = ['S1', 'S2']

    if age in [5.0, 5.5]:
        # For age 5/5.5, both parents need S1 or S2
        father_qualified = father_education in s1_s2_education
        mother_qualified = mother_education in s1_s2_education
        
        if father_qualified and mother_qualified and paud_experience == 'Ya':
            readiness_level = "Siap"
            final_prediction = 85.0
        else:
            readiness_level = "Belum Siap"
            final_prediction = 65.0

    elif age == 6.0:
        # For age 6, different rules based on education levels
        father_basic = father_education in basic_education
        mother_basic = mother_education in basic_education
        father_higher = father_education in higher_education
        mother_higher = mother_education in higher_education

        if father_higher and mother_higher:
            # If both parents have SMA or higher
            readiness_level = "Siap"
            final_prediction = 85.0
        elif father_basic and mother_basic:
            # If both parents have SD or SMP
            if paud_experience == 'Ya':
                readiness_level = "Cukup Siap"
                final_prediction = 75.0
            else:
                readiness_level = "Belum Siap"
                final_prediction = 65.0
        else:
            # Mixed education levels default to higher standard
            if paud_experience == 'Ya':
                readiness_level = "Cukup Siap"
                final_prediction = 75.0
            else:
                readiness_level = "Belum Siap"
                final_prediction = 65.0

    elif age in [6.5, 7.0]:
        # For age 6.5/7, any formal education level qualifies
        father_qualified = father_education in basic_education + higher_education
        mother_qualified = mother_education in basic_education + higher_education
        
        if father_qualified and mother_qualified:
            if paud_experience == 'Ya':
                readiness_level = "Siap"
                final_prediction = 85.0
            else:
                readiness_level = "Cukup Siap"
                final_prediction = 75.0
        else:
            readiness_level = "Belum Siap"
            final_prediction = 65.0
    else:
        readiness_level = "Belum Siap"
        final_prediction = 65.0
    
    return final_prediction, readiness_level

@app.route('/export', methods=['GET'])
@login_required
def export_predictions():
    predictions = get_daily_predictions()
    if not predictions:
        return jsonify({'success': False, 'error': 'No predictions data available'})

    # Create temporary directory for exports if it doesn't exist
    temp_dir = os.path.join(os.getcwd(), 'temp_exports')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Create CSV file with today's date in temp directory
    today = datetime.now().strftime("%Y%m%d")
    filename = f'prediksi_kesiapan_siswa_{today}.csv'
    filepath = os.path.join(temp_dir, filename)
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['name', 'age', 'gender', 'father_education', 'mother_education', 
                         'paud_experience', 'prediction', 'readiness_level', 'timestamp']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for record in predictions:
                writer.writerow(record)

        # Send file and clean up afterwards
        def remove_file(response):
            try:
                os.remove(filepath)
            except OSError:
                pass
            return response

        return send_file(filepath,
                        mimetype='text/csv',
                        as_attachment=True,
                        download_name=filename), {'Cache-Control': 'no-cache'}
    
    except Exception as e:
        # Clean up file if it exists
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        return jsonify({'success': False, 'error': f'Error creating export file: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
