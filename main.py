# ---------------------------- IMPORT STATEMENTS ------------------------------- #
from flask import Flask, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError
from flask_wtf import FlaskForm
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_ckeditor import CKEditor
from wtforms import StringField, SubmitField, DateField, SelectField, PasswordField
from wtforms.validators import DataRequired, ValidationError
import datetime as dt
import os
# ---------------------------- START FLASK FRAMEWORK ------------------------------- #
app = Flask(__name__)
Bootstrap5(app)
app.config['SECRET_KEY'] = os.environ.get('Your_Key')
# ---------------------------- CONNECT TO DATABASE ------------------------------- #
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///to-dos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ---------------------------- DATABASE SETUP ------------------------------- #
class Categories(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    to_dos_category = relationship("ToDos", back_populates="parent_category")

    def __repr__(self):
        """returns name of Category when printed instead of <Categories ID>"""
        return self.name


class ToDos(db.Model):
    __tablename__ = "to_dos"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    parent_category = relationship("Categories", back_populates="to_dos_category")
    due_date = db.Column(db.Date)
    parent_user = relationship("User", back_populates="user_to_dos")

    def __repr__(self):
        """returns name of To Do when printed instead of <ToDos ID>"""
        return self.name


class GotDones(db.Model):
    __tablename__ = "got_dones"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    category = db.Column(db.String(250), nullable=False)
    date = db.Column(db.Date)

    def __repr__(self):
        """returns name of GotDone when printed instead of <GotDones ID>"""
        return self.name


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("to_dos.id"))

    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    user_to_dos = relationship("ToDos", back_populates="parent_user")


with app.app_context():
    db.create_all()


# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# ---------------------------- CREATE FORMS ------------------------------- #
def date_check(form, field):
    """custom validator to check date in wtform entry is not before today's date, raise Validation Error if it is"""
    if field.data < dt.datetime.now().date():
        raise ValidationError("Due Date can't be in the past!")


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired()])
    submit = SubmitField('Add Category')


class UpdateCategoryForm(FlaskForm):
    name = StringField('New Category Name', validators=[DataRequired()])
    submit = SubmitField('Update Category')


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Sign Me Up!")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In!")
# ---------------------------- CREATE ROUTES ------------------------------- #
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))
        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for("dashboard"))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('dashboard'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('dashboard'))


@app.route('/', methods=["GET", "POST"])
def dashboard():
    """renders index.html, calls all ToDos saved in the DB and shows an overview of each To Do"""
    if not current_user.is_authenticated:
        flash("You need to login or register to comment.")
        return redirect(url_for("login"))
    else:
        to_dos = db.session.query(ToDos).all()
        return render_template('index.html', all_to_dos=to_dos)


@app.route('/add-new-category', methods=["GET", "POST"])
def add_new_category():
    """renders 'add-new-category.html', if form is filled out and submitted, gets data from user input and saves it
    as new Category in the DB, redirects to show-category.html"""
    form = CategoryForm()
    if form.validate_on_submit():
        new_category = Categories(
            name=form.name.data
        )
        try:
            db.session.add(new_category)
            db.session.commit()

        except IntegrityError:
            flash("This Category already exists!")
        return redirect(url_for('show_category', category=new_category.name))
    else:
        return render_template('add-new-category.html', form=form)


@app.route('/show-category/<category>')
def show_category(category):
    """renders show-category.html, calls requested Category from the DB and shows all related To Dos"""
    requested_category = Categories.query.filter_by(name=category).first()
    id = requested_category.id
    return render_template('show-category.html', category=requested_category)


@app.route('/all-categories')
def all_categories():
    """renders all-categories.html, calls all Categories from the DB"""
    categories = db.session.query(Categories).all()
    return render_template('all-categories.html', categories=categories)


@app.route('/all-to-dos')
def all_to_dos():
    """renders all-categories.html, calls all Categories from the DB"""
    to_dos = db.session.query(ToDos).all()
    return render_template('all-to-dos.html', to_dos=to_dos)

@app.route('/add-new-to-do', methods=["GET", "POST"])
def add_new_to_do():
    """renders 'add-new-to-do.html', if ToDoForm is filled out and submitted, gets data from user input and saves it
    as new To Do in the DB table to_dos, redirects to show-to-do.html"""
    categories = db.session.query(Categories).all()

    # ToDoForm setup withing function to be able to call newly created categories for SelectField
    class ToDoForm(FlaskForm):
        name = StringField('To Do Name', validators=[DataRequired()])
        category = SelectField('Category', choices=categories, validators=[DataRequired()])
        due_date = DateField('Due Date', validators=[DataRequired(), date_check])
        submit = SubmitField('Add To Do')
    form = ToDoForm()
    if form.validate_on_submit():
        category = Categories.query.filter_by(name=form.category.data).first()
        new_to_do = ToDos(
            name=form.name.data,
            parent_category=category,
            due_date=form.due_date.data)
        db.session.add(new_to_do)
        db.session.commit()
        return redirect(url_for('show_to_do', to_do_id=new_to_do.id))
    else:
        return render_template('add-new-to-do.html', form=form)


@app.route('/show-to-do/<int:to_do_id>')
def show_to_do(to_do_id):
    """renders show-to-do.html, calls requested To Do from the DB and shows all info, including SubTasks"""
    requested_to_do = db.session.get(ToDos, to_do_id)
    return render_template('show-to-do.html', to_do=requested_to_do)


@app.route('/update-to-do/<int:to_do_id>', methods=["GET", "POST"])
def update_to_do(to_do_id):
    """renders update-to-do.html with UpdateToDoForm, defaults set with data for To Do from the DB, if form is
    submitted, updates data for To Do and SubTask in DB"""
    to_do_update = db.session.get(ToDos, to_do_id)
    categories = db.session.query(Categories).all()

    class UpdateToDoForm(FlaskForm):
        name = StringField('To Do Name', validators=[DataRequired()], default=to_do_update.name)
        category = SelectField('Category', choices=categories, validators=[DataRequired()],
                               default=to_do_update.parent_category)
        due_date = DateField('Due Date', validators=[DataRequired(), date_check], default=to_do_update.due_date)
        submit = SubmitField('Update To Do')
    form = UpdateToDoForm()
    category = Categories.query.filter_by(name=form.category.data).first()
    if form.validate_on_submit():
        to_do_update.name = form.name.data
        to_do_update.parent_category = category
        to_do_update.due_date = form.due_date.data
        db.session.commit()
        subtask_update = to_do_update.subtasks
        for subtask in subtask_update:
            subtask.category = str(to_do_update.parent_category)
            db.session.commit()
        return redirect(url_for('show_to_do', to_do_id=to_do_update.id, delete=False))
    else:
        return render_template('update-to-do.html', form=form, to_do=to_do_update)


@app.route('/delete/<int:to_do_id>')
def delete(to_do_id):
    """deletes requested To Do from DB table to_dos, gives warning if there are connected SubTasks"""
    requested_to_do = db.session.get(ToDos, to_do_id)
    subtasks = requested_to_do.subtasks
    if subtasks:
        flash("You have subtasks that haven't been done yet!")
        return render_template('show-to-do.html', to_do=requested_to_do, delete=True)
    else:
        db.session.delete(requested_to_do)
        db.session.commit()
        return redirect(url_for('dashboard'))


@app.route('/update-category/<int:category_id>', methods=["GET", "POST"])
def update_category(category_id):
    """renders update-category.html with UpdateCategoryForm, if form is submitted, updates data for Category in DB"""
    category_update = db.session.get(Categories, category_id)
    form = UpdateCategoryForm()
    if form.validate_on_submit():
        category_update.name = form.name.data
        db.session.commit()
        return redirect(url_for('show_category', category=category_update))
    else:
        return render_template('update-category.html', form=form, category=category_update)


@app.route('/mark-done/<int:to_do_id>')
def mark_done(to_do_id):
    """calls requested to_do from DB table to_dos and all related SubTasks, saves them in DB table got_dones,
    redirects to delete.html"""
    requested_to_do = db.session.get(ToDos, to_do_id)
    new_got_done = GotDones(
        name=requested_to_do.name,
        category=str(requested_to_do.parent_category),
        date=dt.datetime.now().date()
    )

    db.session.add(new_got_done)
    db.session.delete(requested_to_do)
    db.session.commit()
    return redirect(url_for('dashboard', to_do_id=to_do_id))


@app.route('/got-done')
def got_done():
    """renders got-done.html, calls all GotDones saved in the DB and shows an overview"""
    got_dones = db.session.query(GotDones).order_by(desc(GotDones.date))
    return render_template('got-done.html', all_got_dones=got_dones)


@app.route('/clear-got-done')
def clear_got_done():
    """clears all data from DB table got_dones"""
    data_to_delete = db.session.query(GotDones).all()
    for data in data_to_delete:
        db.session.delete(data)
        db.session.commit()
    return redirect(url_for('got_done'))


@app.route('/delete-with-sub/<int:to_do_id>')
def delete_to_do(to_do_id):
    """deletes requested To Do and all related SubTasks from DB"""
    requested_to_do = db.session.get(ToDos, to_do_id)
    db.session.delete(requested_to_do)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/clear-got-done')
def clear_categories():
    """clears all data from DB table got_dones"""
    categories_to_delete = db.session.query(Categories).all()
    for category in categories_to_delete:
        db.session.delete(category)
        db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)