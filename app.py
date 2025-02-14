from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime

app = Flask(__name__)

# SQLite データベース設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# スタッフ情報テーブル
class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

# 出勤・退勤データテーブル
class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)  # 外部キーを正しく定義
    date = db.Column(db.Date, nullable=False)
    check_in = db.Column(db.Time, nullable=True)
    check_out = db.Column(db.Time, nullable=True)

# データベースの作成関数
def init_db():
    with app.app_context():
        db.drop_all()  # 既存のテーブルを削除
        db.create_all()  # 新しいテーブルを作成
        print("データベースを再作成しました。")

init_db()  # アプリ起動時にDBを作成

@app.route("/", methods=["GET", "POST"])
def index():
    staff_list = Staff.query.all()

    if request.method == "POST":
        staff_id = int(request.form["staff_id"])  # int に変換
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

@app.route("/report")
def report():
    monthly_data = db.session.query(
        Staff.name, 
        func.strftime('%Y-%m', Attendance.date).label("month"),
        func.sum((func.julianday(Attendance.check_out) - func.julianday(Attendance.check_in)) * 24)
    ).join(Staff).filter(Attendance.check_out.isnot(None)).group_by(Staff.name, "month").all()

    return render_template("report.html", monthly_data=monthly_data)

if __name__ == "__main__":
    app.run(debug=True)
