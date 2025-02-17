import os
import csv
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_secret_key"  # セッション管理用の秘密鍵

# ✅ データベースのパスを設定
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "database.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)  # instance/ フォルダを自動作成

# ✅ スタッフ情報のテーブル
class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

# ✅ 出勤・退勤データのテーブル
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.Time, nullable=True)
    check_out = db.Column(db.Time, nullable=True)

# ✅ データベースを初期化
def init_db():
    with app.app_context():
        db.create_all()
        print("データベースを作成しました。")

init_db()

# ✅ 管理者ログインページ
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "niida" and password == "admin":
            session["admin"] = True
            flash("ログイン成功", "success")
            return redirect(url_for("staff_management"))
        else:
            flash("ログイン失敗", "danger")
    return render_template("login.html")

# ✅ ログアウト
@app.route("/logout")
def logout():
    session.pop("admin", None)
    flash("ログアウトしました", "success")
    return redirect(url_for("login"))

# ✅ スタッフ管理画面（管理者のみアクセス可能）
@app.route("/staff", methods=["GET", "POST"])
def staff_management():
    if "admin" not in session:
        flash("ログインしてください", "danger")
        return redirect(url_for("login"))

    staff_list = Staff.query.all()
    if request.method == "POST":
        name = request.form["name"]
        if name:
            new_staff = Staff(name=name)
            db.session.add(new_staff)
            db.session.commit()
            flash("スタッフを追加しました", "success")
            return redirect(url_for("staff_management"))
    return render_template("staff.html", staff_list=staff_list)

# ✅ スタッフ削除
@app.route("/staff/delete/<int:staff_id>")
def delete_staff(staff_id):
    if "admin" not in session:
        flash("ログインしてください", "danger")
        return redirect(url_for("login"))
    
    staff = Staff.query.get(staff_id)
    if staff:
        db.session.delete(staff)
        db.session.commit()
        flash("スタッフを削除しました", "success")
    return redirect(url_for("staff_management"))

## ✅ ホーム画面（出勤・退勤の打刻）
@app.route("/", methods=["GET", "POST"])
def index():
    staff_list = Staff.query.all()

    if request.method == "POST":
        staff_id = int(request.form["staff_id"])
        date = datetime.today().date()
        existing_record = Attendance.query.filter_by(staff_id=staff_id, date=date).first()

        if "check_in" in request.form:
            if not existing_record:
                new_entry = Attendance(staff_id=staff_id, date=date, check_in=datetime.now().time())
                db.session.add(new_entry)
                db.session.commit()
        elif "check_out" in request.form and existing_record:
            existing_record.check_out = datetime.now().time()
            db.session.commit()

        return redirect(url_for("index"))

    records = db.session.query(Attendance, Staff).join(Staff).all()
    return render_template("index.html", records=records, staff_list=staff_list)

# ✅ **修正ページ（打刻の編集）**
@app.route("/edit/<int:attendance_id>", methods=["GET", "POST"])
def edit(attendance_id):
    record = Attendance.query.get(attendance_id)

    if not record:
        return "データが見つかりませんでした", 404  # エラーメッセージを表示

    if request.method == "POST":
        record.check_in = datetime.strptime(request.form["check_in"], "%H:%M").time()
        record.check_out = datetime.strptime(request.form["check_out"], "%H:%M").time()
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("edit.html", record=record)

 # ✅ 月ごとの勤務時間の集計
@app.route("/report")
def report():
    monthly_data = db.session.query(
        Staff.name, 
        func.strftime('%Y-%m', Attendance.date).label("month"),
        func.sum((func.julianday(Attendance.check_out) - func.julianday(Attendance.check_in)) * 24)
    ).join(Staff).filter(Attendance.check_out.isnot(None)).group_by(Staff.name, "month").all()

    return render_template("report.html", monthly_data=monthly_data)

# ✅ **CSVファイルをエクスポート**
@app.route("/export/csv")
def export_csv():
    file_path = os.path.join(BASE_DIR, "instance", "attendance.csv")
    
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["名前", "日付", "出勤時間", "退勤時間"])

        records = db.session.query(Attendance, Staff).join(Staff).all()
        for record, staff in records:
            writer.writerow([staff.name, record.date, record.check_in, record.check_out])

    return send_file(file_path, as_attachment=True)

# ✅ **Excelファイルをエクスポート**
@app.route("/export/excel")
def export_excel():
    file_path = os.path.join(BASE_DIR, "instance", "attendance.xlsx")
    
    records = db.session.query(Attendance, Staff).join(Staff).all()
    data = [[staff.name, record.date, record.check_in, record.check_out] for record, staff in records]

    df = pd.DataFrame(data, columns=["名前", "日付", "出勤時間", "退勤時間"])
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ✅ **ログイン制御の確認**
@app.before_request
def require_login():
    restricted_routes = ["staff_management", "delete_staff"]
    if request.endpoint in restricted_routes and "admin" not in session:
        flash("ログインが必要です", "danger")
        return redirect(url_for("login"))

# ✅ Flaskアプリの起動（スマホからもアクセス可能にする）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
