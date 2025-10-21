from flask import Flask, render_template


from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os, random, string

app = Flask(__name__)
app.secret_key = "supersecret"  # change later

# ✅ Absolute DB path so we always know where loyalty.db is stored
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "loyalty.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ------------------ MODELS ------------------
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    badges = db.Column(db.Integer, default=0)
    reward_claimed = db.Column(db.Boolean, default=False) 

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

class LoyaltyCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('customer.id'))

# app = Flask(__name__)
@app.route("/initdb")
def initdb():
    db.drop_all()
    db.create_all()

    # default restaurant
    rest = Restaurant(
        name="GEIA",
        password_hash=generate_password_hash("chef@123")
    )
    db.session.add(rest)

    # generate 10,000 unique 6-character alphanumeric codes
    codes = set()
    while len(codes) < 10000:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        codes.add(code)

    # save in DB
    for c in codes:
        db.session.add(LoyaltyCode(code=c))

    db.session.commit()

    # also save in CSV
    csv_path = os.path.join(BASE_DIR, "codes.csv")
    with open(csv_path, "w") as f:
        f.write("LoyaltyCode\n")
        for c in codes:
            f.write(c + "\n")

    return f"Database initialized with {len(codes)} codes. Exported to {csv_path}"

@app.route("/loyalty", methods=["GET", "POST"])
def loyalty():
    if request.method == "POST":
        mobile = request.form["mobile"]
        customer = Customer.query.filter_by(mobile=mobile).first()
        if customer:
            return redirect(url_for("badges", mobile=mobile))
        else:
            new_cust = Customer(mobile=mobile, badges=0)
            db.session.add(new_cust)
            db.session.commit()
            flash("Your account has been created successfully 🥳 ", "success")
            return redirect(url_for("badges", mobile=mobile))
    return render_template("loyalty_welcome.html")


@app.route("/badges")
def badges():
    mobile = request.args.get("mobile")
    customer = Customer.query.filter_by(mobile=mobile).first()
    if not customer:
        return redirect(url_for("loyalty"))
    return render_template("loyalty_badges.html", customer=customer)
@app.route("/restaurant/login", methods=["GET", "POST"])
def restaurant_login():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        rest = Restaurant.query.filter_by(name=name).first()
        if rest and check_password_hash(rest.password_hash, password):
            session["restaurant"] = rest.id
            return redirect(url_for("restaurant_panel"))
        flash("Invalid login.!", "danger")
    return render_template("restaurant_login.html")
@app.route("/restaurant/panel", methods=["GET", "POST"])
def restaurant_panel():
    if "restaurant" not in session:
        return redirect(url_for("restaurant_login"))

    message = None
    customer = None

    if request.method == "POST":
        mobile = request.form.get("mobile")
        action = request.form.get("action")
        code = request.form.get("code")

        customer = Customer.query.filter_by(mobile=mobile).first()

        if not customer:
            message = "Customer not found..!"
        elif action == "apply":
            code_obj = LoyaltyCode.query.filter_by(code=code, is_used=False).first()
            if not code_obj:
                message = "Invalid or already used code.!"
            else:
                customer.badges = min(customer.badges + 1, 10)
                code_obj.is_used = True
                code_obj.used_by = customer.id
                db.session.commit()
                message = f"Badge added! Customer now has {customer.badges}/10 badges."
        elif action == "claim":
            if customer.badges == 10 and not customer.reward_claimed:
                customer.reward_claimed = True
                customer.badges = 0   # reset for next cycle
                db.session.commit()
                message = f"Reward claimed for {mobile} ✅"
            else:
                message = "Reward cannot be claimed yet."

    return render_template("restaurant_panel.html", message=message, customer=customer)

@app.route("/")
def index():
    return render_template("index.html")
@app.route("/menu")
def menu():
    return render_template("menu.html")
@app.route("/review")
def review():
    return render_template("review.html")



if __name__ == "__main__":
    app.run(debug=True)
