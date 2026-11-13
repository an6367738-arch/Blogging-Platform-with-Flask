
from flask import (
    Flask, render_template, redirect,
    url_for, request, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from datetime import datetime

app = Flask(__name__, template_folder="html_pages")
app.config.from_object(Config)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# USER MODEL
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    posts = db.relationship("Post", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="commenter", lazy=True)


# BLOG POST MODEL
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(
        db.DateTime, default=datetime.utcnow
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    comments = db.relationship(
        "Comment", backref="post", lazy=True,
        cascade="all, delete-orphan"
    )


# COMMENT MODEL
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# HOME PAGE AND SEARCH
@app.route("/")
def index():
    search = request.args.get("search", "").strip()

    query = Post.query

    if search:
        query = query.filter(
            db.or_(
                Post.title.ilike(f"%{search}%"),
                Post.content.ilike(f"%{search}%")
            )
        )

    posts = query.order_by(Post.date_created.desc()).all()

    return render_template("index.html", posts=posts, search=search)


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or len(password) < 8:
            flash("Enter all details. Password must be at least 8 characters.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("register"))

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Welcome back!", "success")

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)

            return redirect(url_for("index"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# LOGOUT
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "success")
    return redirect(url_for("index"))


# CREATE POST
@app.route("/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("create_post"))

        post = Post(
            title=title,
            content=content,
            user_id=current_user.id
        )

        db.session.add(post)
        db.session.commit()

        flash("Blog post created successfully!", "success")
        return redirect(url_for("index"))

    return render_template("create_post.html")


# VIEW SINGLE POST
@app.route("/post/<int:post_id>")
def view_post(post_id):
    post = db.get_or_404(Post, post_id)
    return render_template("post.html", post=post)


# EDIT POST
@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = db.get_or_404(Post, post_id)

    if post.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("edit_post", post_id=post.id))

        post.title = title
        post.content = content
        db.session.commit()

        flash("Post updated successfully!", "success")
        return redirect(url_for("view_post", post_id=post.id))

    return render_template("create_post.html", post=post)


# DELETE POST
@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)

    if post.user_id != current_user.id:
        abort(403)

    db.session.delete(post)
    db.session.commit()

    flash("Post deleted successfully!", "success")
    return redirect(url_for("index"))


# ADD COMMENT
@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def add_comment(post_id):
    post = db.get_or_404(Post, post_id)
    content = request.form.get("content", "").strip()

    if not content:
        flash("Comment cannot be empty.", "danger")
        return redirect(url_for("view_post", post_id=post.id))

    comment = Comment(
        content=content,
        user_id=current_user.id,
        post_id=post.id
    )

    db.session.add(comment)
    db.session.commit()

    flash("Comment added successfully!", "success")
    return redirect(url_for("view_post", post_id=post.id))


# DELETE COMMENT
@app.route("/comment/delete/<int:comment_id>", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)

    if comment.user_id != current_user.id and comment.post.user_id != current_user.id:
        abort(403)

    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()

    flash("Comment deleted.", "success")
    return redirect(url_for("view_post", post_id=post_id))


# CREATE DATABASE AND RUN
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
