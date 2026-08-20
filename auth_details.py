import sqlite3
import hashlib

conn = sqlite3.connect("hospital.db", check_same_thread=False)
cursor = conn.cursor()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------- Login ----------------

def login_user(email, password):

    password = hash_password(password)

    cursor.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, password)
    )

    return cursor.fetchone()


# ---------------- Patient Register ----------------

def register_patient(name, email, password, phone, gender, age):

    password = hash_password(password)

    try:

        cursor.execute(
            """
            INSERT INTO users
            (name,email,password,role,phone,gender,age)
            VALUES(?,?,?,?,?,?,?)
            """,

            (
                name,
                email,
                password,
                "Patient",
                phone,
                gender,
                age
            )
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False


# ---------------- Admin Add Doctor ----------------

def add_doctor(name, email, password, phone, department):

    password = hash_password(password)

    cursor.execute(
        """
        INSERT INTO users
        (name,email,password,role,phone,department)
        VALUES(?,?,?,?,?,?)
        """,

        (
            name,
            email,
            password,
            "Doctor",
            phone,
            department
        )
    )

    conn.commit()