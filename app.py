from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from functools import wraps
import pandas as pd
import pickle
from sklearn.tree import DecisionTreeRegressor
from sklearn.preprocessing import LabelEncoder
import csv
from datetime import datetime
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for session management

# Login credentials
VALID_USERNAME = "admin"
VALID_PASSWORD = "12345678"

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

        # Implement new prediction logic based on user feedback
        readiness_level = "Belum Siap"
        final_prediction = 0.0

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

@app.route('/export', methods=['GET'])
@login_required
def export_predictions():
    predictions = get_daily_predictions()
    if not predictions:
        return jsonify({'success': False, 'error': 'No predictions data available'})

    # Create CSV file with today's date
    today = datetime.now().strftime("%Y%m%d")
    filename = f'prediksi_kesiapan_siswa_{today}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'age', 'gender', 'father_education', 'mother_education', 
                     'paud_experience', 'prediction', 'readiness_level', 'timestamp']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for record in predictions:
            writer.writerow(record)

    return send_file(filename,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
