import os, time, cv2, random, string
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from datetime import datetime


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///videos.db'
app.config['SECRET_KEY'] = '\xff\xb4\xb4\xb7+R\x06\x8f\xfd\xe06\x99\x92\xc1\xb2\xe7\x92*\x97\xdd\x07k\xd3I'
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['THUMBNAIL_FOLDER'] = os.path.join(app.root_path, 'static')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
categories = ['Animation', 'Memes', 'Gaming', 'Music', 'Sports', 'News', 'Science', 'Art', 'Nature']

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))

    def get_id(self):
        return self.username 



class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    filename = db.Column(db.String(100))
    thumbnail_filename = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('videos', lazy=True))
    views = db.Column(db.Integer, default=0)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='video', lazy=True)

    def get_id(self):
        return self.filename



class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow) 
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('comments', lazy=True))



@app.route('/category/<category>')
def category(category):
    videos = Video.query.filter_by(category=category).all()
    return render_template('category.html', videos=videos, category=category, categories=categories)


@app.route('/')
def index():
    search_query = request.args.get('search_query')
    if search_query:
        videos = Video.query.filter(Video.title.contains(search_query)).all()
    else:
        videos = Video.query.all()
    
    return render_template('index.html', videos=videos, categories=categories, search_query=search_query)


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(username=user_id).first()


def generate_unique_filename(filename):
    timestamp = str(int(time.time()))
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    unique_filename = f"{timestamp}_{random_string}_{filename}"
    return unique_filename

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        file = request.files['file']

        video_filename = generate_unique_filename(file.filename)
        existing_video = Video.query.filter_by(filename=video_filename, user=current_user).first()
        if existing_video:
            flash('A video with the same filename already exists.', 'danger')
            return redirect(url_for('upload'))

        file.save(os.path.join(app.config['UPLOAD_FOLDER'], video_filename))
        

        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
        thumbnail_filename = f'thumbnail_{video_filename}.jpg'
        thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if not ret or frame is None:
            flash('Failed to read the video frame.', 'danger')
            return redirect(url_for('upload'))

        thumbnail_size = (320, 240)
        thumbnail = cv2.resize(frame, thumbnail_size)
        cv2.imwrite(thumbnail_path, thumbnail)
        cap.release()
        
        video = Video(
            title=title,
            description=description,
            category=category,
            filename=video_filename,
            thumbnail_filename=thumbnail_filename,
            user=current_user
        )

        db.session.add(video)
        db.session.commit()

        flash('Video uploaded successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('upload.html', categories=categories)


@app.route('/video/<string:video_filename>', methods=['GET', 'POST'])
def video(video_filename):
    video = Video.query.filter_by(filename=video_filename).first()

    if request.method == 'POST':
        content = request.form.get('content')

        comment = Comment(content=content, video=video, user=current_user)
        db.session.add(comment)
        db.session.commit()

        flash('Comment added successfully!', 'success')
        return redirect(url_for('video', video_filename=video.filename))
    else:
        video.views += 1
        db.session.commit() 
        return render_template('video.html', video=video, categories=categories)


@app.route('/comment/delete/<int:comment_id>')
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)

    if comment and current_user.id == comment.user_id:
        video = comment.video  
        db.session.delete(comment)
        db.session.commit()
        flash('Comment deleted successfully!', 'success')
    else:
        flash('Comment not found or you are not authorized to delete it.', 'danger')
        return redirect(url_for('video', video_filename=video.filename))

    return redirect(url_for('video', video_filename=video.filename))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Registration successful! You are now logged in.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html', categories=categories)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/user/<string:username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    videos = Video.query.filter_by(user=user).all()
    if user:
        return render_template('user.html', user=user, videos=videos, categories=categories, Video=Video)
    else:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/delete-video/<int:video_id>', methods=['GET', 'POST'])
@login_required
def delete_video(video_id):
    video = Video.query.get(video_id)

    if video and current_user.id == video.user_id:
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
        thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], video.thumbnail_filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)

        db.session.delete(video)
        db.session.commit()

        flash('Video deleted successfully!', 'success')
    else:
        flash('Video not found or you are not authorized to delete it.', 'danger')

    return redirect(url_for('user', username=current_user.username))


if __name__ == '__main__':
    app.run()