from flask import Flask, render_template, url_for, redirect, request, session, flash, jsonify, g
from pymongo import MongoClient
from bson.objectid import ObjectId
import functools
import bcrypt
import os
from os.path import join, dirname, realpath
from werkzeug.utils import secure_filename
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from bson import ObjectId
from flask_pymongo import PyMongo

client = MongoClient("mongodb://localhost:27017/")
db = client["webapp"]
projects_col = db.projects
posts_col = db.posts
contacts_col = db.contacts
settings_col = db.settings
user_col = db['user']
travel_col = db['travel']

app = Flask(__name__)
app.config["MONGO_URI"] = 'mongodb://localhost:27017/webapp'
mongo = PyMongo(app)
GOOGLE_PLACES_API_KEY = 'AIzaSyD5rHImrtbYm48xEr7agbSZPGbJ_Njti4Q'

PATH_UPLOAD = 'static/uploads'
FULL_UPLOAD_FOLDER = join(dirname(realpath(__file__)), PATH_UPLOAD)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = FULL_UPLOAD_FOLDER
app.secret_key = 'fad62b7c1a6a9e67dbb66c3571a23ff2425650965f80047ea2fadce543b088cf'

def update_setting_data(_id, updatedvalues):
    _id_converted = ObjectId(_id)
    query_by_id = {"_id": _id_converted}
    new_updated_value = { "$set": updatedvalues }
    settings_col.update_one(query_by_id, new_updated_value)

def upload_image_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        generated_datetime = datetime.now().strftime('%Y%m%d%H%M%S%f')
        filename = generated_datetime+"_"+filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    else:
        flash('Allowed image types are -> png, jpg, jpeg, gif')
        return ""

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        user_email = session.get('user_email')
        if user_email is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def skiplimit(col, page_size, page_num, user_email=None):
    skips = page_size * (page_num - 1)
    query = {} if user_email is None else {"user": user_email}
    cursor = col.find(query).sort("_id", -1).skip(skips).limit(page_size)
    return list(cursor)

@app.before_request
def before_request():
    g.current_time = datetime.now()

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'uploadfile' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['uploadfile']
        if file.filename == '':
            flash('No image selected for uploading')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            flash('Image successfully uploaded and displayed below')
            return render_template('uploadform.html', filename=filename)
        else:
            flash('Allowed image types are -> png, jpg, jpeg, gif')
            return redirect(request.url)
        
    return render_template('uploadform.html')

@app.route('/display/<filename>')
def display_image(filename):
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

def refreshSettingSessionData():
    setting_data = settings_col.find_one()
    session["website_name"] = setting_data["website_name"]
    session["tagline"] = setting_data["tagline"]

@app.route('/')
def index():
    website_name = session.get('website_name')
    if (website_name is None):
        refreshSettingSessionData()

    post_data = posts_col.find({}).sort("_id", -1).limit(3)
    post_data_list = list(post_data)
    project_data = projects_col.find({}).sort("_id", -1).limit(2)
    project_data_list = list(project_data)
    
    return render_template("home.html", posts=post_data_list, projects=project_data_list)

@app.route('/travel')
def travel_plan():
    return render_template('travel.html')

@app.route('/api/travel/cities')
def get_cities():
    cities = list(travel_col.find({}, {'_id': 0}))  # _id를 제외한 모든 데이터를 가져옵니다.
    return jsonify(cities)

@app.route('/about')
def about():
    about_data = settings_col.find_one()
    return render_template("about.html", data=about_data)

@app.route('/projects')
def projects():
    project_data = projects_col.find({}).sort("_id", -1)
    project_data_list = list(project_data)
    return render_template("projects.html", data=project_data_list)

@app.route('/projects/detail/<id>')
def projects_detail(id):
    project_data = ""
    try:
        _id_converted = ObjectId(id)
        search_filter = {"_id": _id_converted}
        project_data = projects_col.find_one(search_filter)
    except:
        print("ID is not found/invalid")
    
    return render_template("projects_detail.html", data=project_data)

@app.route('/posts')
def posts():
    page_size = 10
    page_num = request.args.get('page')
    if page_num is None:
        page_num = 1
    else:
        page_num = int(page_num)

    data = skiplimit(posts_col, page_size, page_num)
    
    last_data = False
    if len(data) == 0:
        last_data = True

    for post in data:
        if 'views' not in post:
            post['views'] = 0
        if 'likes' not in post:
            post['likes'] = 0

    return render_template("posts.html", data=data, page=page_num, last_data=last_data)

@app.route('/posts/detail/<id>')
@login_required
def posts_detail(id):
    post_data = ""
    try:
        _id_converted = ObjectId(id)
        search_filter = {"_id": _id_converted}
        post_data = posts_col.find_one(search_filter)
        if post_data:
            posts_col.update_one(search_filter, {"$inc": {"views": 1}})
    except:
        print("ID is not found/invalid")

    return render_template("posts_detail.html", data=post_data)

@app.route('/new_post', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form['title'].strip()
        tags = request.form['tags'].strip()
        content = request.form['content'].strip()
        author = session['user_email']

        # HTML 태그 제거
        soup = BeautifulSoup(content, "html.parser")
        content_text_only = soup.get_text()
        
        image_filename = ''
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                image_filename = upload_image_file(file)
        
        new_post_data = {
            "title": title,
            "tags": tags,
            "content": content_text_only,  # HTML 태그가 제거된 콘텐츠
            "author": author,
            "created_date": datetime.now(),
            "views": 0,
            "likes": 0,
            "image": image_filename
        }
        posts_col.insert_one(new_post_data)
        flash("Post created successfully.")
        return redirect(url_for('posts'))

    return render_template('new_post.html')

@app.route('/posts/comment/new/<id>', methods=['POST'])
def new_comment(id):
    _id = request.form['_id'].strip()
    email = request.form['email'].strip()
    name = request.form['name'].strip()
    content = request.form['content'].strip()

    new_comment = { "email": email, "name": name, "content": content, "created_date": datetime.now() }

    _id_converted = ObjectId(_id)
    search_filter = {"_id": _id_converted}
    post_data = posts_col.find_one(search_filter)
    
    comments = list()
    
    if post_data.__contains__("comments"):
        comments = list(post_data['comments'])

    comments.append(new_comment.copy())

    query_by_id = {"_id": _id_converted}
    new_updated_comments = { "$set": { "comments": comments } }
    posts_col.update_one(query_by_id, new_updated_comments)

    flash("Your comment has been successfully received.")
    return redirect(url_for('posts_detail', id=id))

@app.route('/posts/recommend/<id>', methods=['POST'])
@login_required
def recommend_post(id):
    user_email = session['user_email']
    try:
        _id_converted = ObjectId(id)
        search_filter = {"_id": _id_converted}
        post_data = posts_col.find_one(search_filter)
        
        if post_data:
            if 'recommendations' not in post_data:
                post_data['recommendations'] = []
            
            if user_email not in post_data['recommendations']:
                new_likes = post_data.get('likes', 0) + 1
                post_data['recommendations'].append(user_email)
                
                posts_col.update_one(search_filter, {
                    "$set": {
                        "likes": new_likes,
                        "recommendations": post_data['recommendations']
                    }
                })
                flash("Thank you for recommending this post!")
            else:
                flash("You have already recommended this post.", "info")
        else:
            flash("Post not found.", "error")
    except:
        flash("An error occurred. Please try again.", "error")

    return redirect(url_for('posts_detail', id=id))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == "POST":
        email = request.form['email'].strip()
        subject = request.form['subject'].strip()
        name = request.form['name'].strip()
        content = request.form['content'].strip()

        new_contact_data = { "email": email, "subject": subject, "name": name, "content": content, "created_date": datetime.now() }
        contacts_col.insert_one(new_contact_data)
        return render_template("thankyou.html")

    return render_template("contact.html")

def update_project_data(_id, updatedvalues):
    _id_converted = ObjectId(_id)
    query_by_id = {"_id": _id_converted}
    new_updated_value = { "$set": updatedvalues }
    projects_col.update_one(query_by_id, new_updated_value)

@app.route('/admin/posts')
@login_required
def admin_posts():
    posts_data = posts_col.find({}).sort("_id", -1)
    posts_data_list = list(posts_data)
    return render_template("admin/posts.html", data=posts_data_list)

@app.route('/admin/posts/new', methods=['GET', 'POST'])
@login_required
def admin_new_post():
    if request.method == 'POST':
        file = request.files['image']
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        content = request.form['content'].strip()
        
        new_data = { "title": title, "author": author, "content": content, "created_date": datetime.now()}
        
        if file.filename != '':
            image_filename = upload_image_file(file)
            if image_filename:
                new_data["image"] = image_filename
        posts_col.insert_one(new_data)
        flash("The data has been successfully saved.")
        return redirect(url_for('admin_posts'))

    return render_template("admin/new_post.html")

@app.route('/admin/posts/update/<id>', methods=['GET', 'POST'])
@login_required
def admin_update_post(id):
    if request.method == 'POST':
        file = request.files['image']
        _id = request.form['_id'].strip()
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        content = request.form['content'].strip()

        updatedvalues = { "title": title, "author": author, "content": content}
        
        if file.filename != '':
            image_filename = upload_image_file(file)
            if image_filename:
                updatedvalues["image"] = image_filename
        update_post_data(id, updatedvalues)
        flash("The data has been successfully updated.")
        return redirect(url_for('admin_posts'))

    data = ""
    try:
        _id_converted = ObjectId(id)
        search_filter = {"_id": _id_converted}
        data = posts_col.find_one(search_filter)
    except:
        print("ID is not found/invalid")

    return render_template("admin/update_post.html", data=data)

def update_post_data(_id, updatedvalues):
    _id_converted = ObjectId(_id)
    query_by_id = {"_id": _id_converted}
    new_updated_value = { "$set": updatedvalues }
    posts_col.update_one(query_by_id, new_updated_value)

@app.route('/admin/posts/delete/<id>', methods=['POST'])
@login_required
def admin_delete_post(id):
    if request.method == "POST":
        _id_converted = ObjectId(id)
        query_by_id = {"_id": _id_converted}
        posts_col.delete_one(query_by_id)
        flash("The data has been successfully deleted.")
        return redirect(url_for('admin_posts'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if request.method == 'POST':
        file = request.files['profile_img']
        _id = request.form['_id'].strip()
        website_name = request.form['website_name'].strip()
        tagline = request.form['tagline'].strip()
        about = request.form['about'].strip()

        updatedvalues = { "website_name": website_name, "tagline": tagline, "about": about }
        
        if file.filename != '':
            image_filename = upload_image_file(file)
            if image_filename:
                updatedvalues["profile_img"] = image_filename
        update_setting_data(_id, updatedvalues)
        refreshSettingSessionData()
        flash("The data has been successfully updated.")
        return redirect(url_for('admin_settings'))

    setting_data = settings_col.find_one()
    return render_template("admin/settings.html", data=setting_data)

@app.route('/sign', methods=['GET', 'POST'])
def sign_in():
    if request.method == "POST":
        _id = request.form['Id/Email'].strip()
        password = request.form['password'].strip()
        password2 = request.form['password2'].strip()
        if password == password2:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            new_user_info = {"email": _id, "password": hashed_password.decode('utf-8')}
            user_col.insert_one(new_user_info)
            return redirect(url_for('login'))
        else:
            flash('비밀번호가 일치하지 않습니다.', 'error')
            return redirect(url_for('sign_in'))
    return render_template("sign.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        user_data = user_col.find_one({"email": email})
        
        if user_data:
            user_data_password = user_data['password']
            
            if bcrypt.checkpw(password.encode('utf-8'), user_data_password.encode('utf-8')):
                session["user_email"] = email
                return redirect(url_for('index'))
            else:
                flash('Email/password is invalid. Please try again.')
                return redirect(url_for('login'))
        
        flash('로그인에 실패했습니다. 비밀번호가 일치하지 않습니다.', 'error')
        return redirect(url_for('login'))
    
    user_email = session.get('user_email')
    if user_email:
        return redirect(url_for('admin_posts'))
    
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/editor')
@login_required
def editor():
    return render_template('index.html')

@app.route('/plan')
@login_required
def plan():
    return render_template('plan.html')

@app.route('/api/places', methods=['GET'])
def get_places():
    location = request.args.get('location')
    place_type = request.args.get('type')
    if not location or not place_type:
        return jsonify({'error': '위치와 유형은 필수입니다.'}), 400
    places = fetch_places_from_google(location, place_type)
    return jsonify(places)

def fetch_places_from_google(location, place_type):
    url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': f'{location} {place_type}',
        'key': GOOGLE_PLACES_API_KEY,
        'language': 'ko'
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return []
    
    results = response.json().get('results', [])
    filtered_results = [
        {
            'name': result['name'],
            'type': place_type,
            'rating': result['rating'],
            'address': result.get('formatted_address', 'N/A'),
            'location': result['geometry']['location'],
            'place_id': result['place_id']
        }
        for result in results
        if result.get('rating', 0) >= 4.0 and result.get('user_ratings_total', 0) > 10
    ]
    limit = 20 if place_type == 'tourist_attraction' else 10
    return filtered_results[:limit]

@app.route('/api/place_details', methods=['GET'])
def get_place_details():
    place_id = request.args.get('place_id')
    if not place_id:
        return jsonify({'error': 'place_id is required'}), 400

    place_details = fetch_place_details_from_google(place_id)
    if place_details:
        return jsonify(place_details)
    return jsonify({'error': 'Place not found'}), 404

def fetch_place_details_from_google(place_id):
    url = 'https://maps.googleapis.com/maps/api/place/details/json'
    params = {
        'place_id': place_id,
        'key': GOOGLE_PLACES_API_KEY,
        'language': 'ko',
        'fields': 'name,rating,formatted_address,formatted_phone_number,opening_hours,photos'
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    
    result = response.json().get('result')
    if not result:
        return None

    photo_url = ''
    if result.get('photos'):
        photo_reference = result['photos'][0]['photo_reference']
        photo_url = f'https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={GOOGLE_PLACES_API_KEY}'

    return {
        'name': result['name'],
        'rating': result.get('rating', 'N/A'),
        'address': result.get('formatted_address', 'N/A'),
        'phone_number': result.get('formatted_phone_number', 'N/A'),
        'opening_hours': ', '.join(result['opening_hours']['weekday_text']) if result.get('opening_hours') else 'N/A',
        'photo_url': photo_url
    }

@app.route('/search_place', methods=['POST'])
def search_place():
    query = request.json['query']
    place = fetch_place_by_query(query)
    if place:
        return jsonify(success=True, place=place)
    return jsonify(success=False, error='장소를 찾을 수 없습니다.')

def fetch_place_by_query(query):
    url = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {
        'query': query,
        'key': GOOGLE_PLACES_API_KEY,
        'language': 'ko'
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return None
    
    results = response.json().get('results', [])
    if not results:
        return None
    
    result = results[0]
    return {
        'name': result['name'],
        'type': 'custom',
        'rating': result.get('rating', 'N/A'),
        'address': result.get('formatted_address', 'N/A'),
        'location': result['geometry']['location'],
        'place_id': result['place_id']
    }

@app.route('/add_place', methods=['POST'])
@login_required
def add_place():
    place = request.json['place']
    place['user'] = session['user_email']
    if mongo.db.custom_places.find_one({'place_id': place['place_id'], 'user': place['user']}):
        return jsonify(success=False, error='이미 일정에 추가된 장소입니다.')
    
    result = mongo.db.custom_places.insert_one(place)
    place['_id'] = str(result.inserted_id)
    return jsonify(success=True, place=place)

@app.route('/delete_place', methods=['POST'])
@login_required
def delete_place():
    place_id = request.json['_id']
    if not ObjectId.is_valid(place_id):
        return jsonify(success=False, error='Invalid place ID'), 400
    
    mongo.db.custom_places.delete_one({'_id': ObjectId(place_id)})
    return jsonify(success=True)

@app.route('/delete_plan', methods=['POST'])
@login_required
def delete_plan():
    plan_id = request.json['_id']
    if not ObjectId.is_valid(plan_id):
        return jsonify(success=False, error='Invalid plan ID'), 400
    
    mongo.db.itineraries.delete_one({'_id': ObjectId(plan_id)})
    return jsonify(success=True)

@app.route('/api/custom_places', methods=['GET'])
@login_required
def get_custom_places():
    user_email = session.get('user_email')
    places = list(mongo.db.custom_places.find({'user': user_email}))
    for place in places:
        place['_id'] = str(place['_id'])
    return jsonify(places)

@app.route('/api/itinerary', methods=['GET'])
@login_required
def get_itinerary():
    user_email = session.get('user_email')
    places = list(mongo.db.custom_places.find({'user': user_email}))
    for place in places:
        place['_id'] = str(place['_id'])
    return jsonify(places)

@app.route('/api/plans', methods=['GET'])
@login_required
def get_plans():
    user_email = session.get('user_email')
    plans = list(mongo.db.itineraries.find({'user': user_email}))
    for plan in plans:
        plan['_id'] = str(plan['_id'])
    return jsonify(plans)

@app.route('/save_itinerary', methods=['POST'])
@login_required
def save_itinerary():
    itinerary_data = request.json
    itinerary_data['user'] = session['user_email']
    title = itinerary_data.get('title')

    existing_itinerary = mongo.db.itineraries.find_one({'title': title, 'user': itinerary_data['user']})
    if (existing_itinerary):
        overwrite = request.json.get('overwrite', False)
        if not overwrite:
            return jsonify(success=False, error='이미 같은 제목의 여행 계획이 있습니다.', overwrite_prompt=True)
        else:
            mongo.db.itineraries.delete_one({'_id': existing_itinerary['_id']})
    
    result = mongo.db.itineraries.insert_one(itinerary_data)
    itinerary_data['_id'] = str(result.inserted_id)
    return jsonify(success=True, itinerary=itinerary_data)

@app.route('/api/plans/<plan_id>', methods=['GET'])
@login_required
def get_plan(plan_id):
    user_email = session.get('user_email')
    plan = mongo.db.itineraries.find_one({'_id': ObjectId(plan_id), 'user': user_email})
    if plan:
        plan['_id'] = str(plan['_id'])
        return jsonify(plan)
    return jsonify(success=False, error='일정을 찾을 수 없습니다.'), 404

if __name__ == '__main__':
    app.run(debug=True)
