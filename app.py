# app.py
import os
from typing import List
import sqlite3
import uuid
import datetime
from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import ai_provider  # <-- will handle Gemini
from passlib.context import CryptContext
import httpx
import json

load_dotenv()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), "artfeed.db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")  # your folder name
# ----------------------------
# Schema helpers
# ----------------------------
def users_has_column(column_name: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    cols = [r[1] for r in c.fetchall()]
    conn.close()
    return column_name in cols


# ----------------------------
# Initialize DB
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Posts table
    c.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT,
        title TEXT,
        idea_text TEXT,
        story TEXT,
        purpose TEXT,
        artist TEXT,
        price TEXT,
        contact TEXT,
        category TEXT,
        created_at TIMESTAMP
    )
    """)
    
    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        bio TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Ensure phone column exists even if table was created previously without it
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass
    # Follows table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS follows (
            follower TEXT NOT NULL,
            artist TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(follower, artist)
        )
        """
    )
    # Likes table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS likes (
            user TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user, post_id),
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
        """
    )
    # Messages table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    
    conn.commit()
    conn.close()

init_db()
# ----------------------------
# Manual migration helper
# ----------------------------
def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Create posts table if missing
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT,
            title TEXT,
            idea_text TEXT,
            story TEXT,
            purpose TEXT,
            artist TEXT,
            price TEXT,
            contact TEXT,
            category TEXT,
            created_at TIMESTAMP
        )
        """
    )
    # Create users table if missing
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            phone TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Add phone column if missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    except sqlite3.OperationalError:
        pass
    # Add bio column if missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN bio TEXT")
    except sqlite3.OperationalError:
        pass
    # Add category column if missing
    try:
        c.execute("ALTER TABLE posts ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass
    # Add images column for multiple images (JSON array)
    try:
        c.execute("ALTER TABLE posts ADD COLUMN images TEXT")
    except sqlite3.OperationalError:
        pass
    # Create follows table if missing
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS follows (
            follower TEXT NOT NULL,
            artist TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(follower, artist)
        )
        """
    )
    # Create likes table if missing
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS likes (
            user TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user, post_id),
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
        """
    )
    # Create messages table if missing
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

@app.get("/admin/migrate")
def admin_migrate():
    ensure_schema()
    # Backfill columns for already-created users table without columns
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not users_has_column("phone"):
        try:
            c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    if not users_has_column("bio"):
        try:
            c.execute("ALTER TABLE users ADD COLUMN bio TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()
    return JSONResponse({"status": "ok", "message": "Schema ensured (users.phone/users.bio present)"})

# ----------------------------
# Helper to insert post
# ----------------------------
def insert_post(image_path, title, idea_text, story, purpose, artist, price, contact, category, images=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Convert images list to JSON string
    images_json = None
    if images:
        import json
        images_json = json.dumps(images)
    
    c.execute(
        "INSERT INTO posts (image_path, title, idea_text, story, purpose, artist, price, contact, category, images, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (image_path, title, idea_text, story, purpose, artist, price, contact, category, images_json, datetime.datetime.utcnow()),
    )
    conn.commit()
    post_id = c.lastrowid
    conn.close()
    return post_id

# ----------------------------
# Follow helpers
# ----------------------------
def follow_artist(follower: str, artist: str) -> bool:
    follower = (follower or "").strip()
    artist = (artist or "").strip()
    if not follower or not artist or follower.lower() == artist.lower():
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO follows (follower, artist) VALUES (?, ?)", (follower.lower(), artist.lower()))
        conn.commit()
        return True
    finally:
        conn.close()

def unfollow_artist(follower: str, artist: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM follows WHERE follower=? AND artist=?", (follower.lower(), artist.lower()))
    conn.commit()
    conn.close()
    return True

def is_following(follower: str, artist: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM follows WHERE follower=? AND artist=?", (follower.lower(), artist.lower()))
    row = c.fetchone()
    conn.close()
    return bool(row)

def is_mutual_follow(user_a: str, user_b: str) -> bool:
    if not user_a or not user_b:
        return False
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT 1 FROM follows WHERE follower=? AND artist=?
        """,
        (user_a.lower(), user_b.lower()),
    )
    f1 = c.fetchone() is not None
    c.execute(
        """
        SELECT 1 FROM follows WHERE follower=? AND artist=?
        """,
        (user_b.lower(), user_a.lower()),
    )
    f2 = c.fetchone() is not None
    conn.close()
    return f1 and f2

# ----------------------------
# Feed & Create Pages
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def feed(request: Request):
    user = request.cookies.get("user")
    return templates.TemplateResponse("feed.html", {"request": request, "user": user})

@app.get("/create", response_class=HTMLResponse)
def create_page(request: Request):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("create.html", {"request": request, "user": user})

@app.get("/generate_art", response_class=HTMLResponse)
def generate_art_page(request: Request):
    user = request.cookies.get("user")
    return templates.TemplateResponse("generate_art.html", {"request": request, "user": user})

# ----------------------------
# Post detail page
# ----------------------------
@app.get("/post/{post_id}", response_class=HTMLResponse)
def post_detail(request: Request, post_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Join posts and users tables to get user email along with post data
    c.execute("""
        SELECT p.id, p.image_path, p.title, p.story, p.artist, p.price, p.contact, p.category, p.created_at, p.images, u.email,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS like_count
        FROM posts p
        LEFT JOIN users u ON LOWER(p.artist) = LOWER(u.username)
        WHERE p.id = ?
    """, (post_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Post not found", status_code=404)
    
    # Parse images (JSON array or fallback to single image)
    images = []
    if row[9]:  # images column
        try:
            import json
            images = json.loads(row[9])
        except:
            images = []
    
    if not images and row[1]:  # fallback to single image
        images = [row[1]]
    
    post = {
        "id": row[0],
        "image": row[1],
        "images": images,
        "title": row[2],
        "story": row[3],
        "artist": row[4],
        "price": row[5],
        "contact": row[6],
        "category": row[7],
        "created_at": row[8],
        "email": row[10],  # Add email from the joined users table
        "like_count": row[11] or 0,
    }
    user = request.cookies.get("user")
    following = is_following(user, post['artist']) if user else False
    
    return templates.TemplateResponse(
        "post_detail.html",
        {"request": request, "user": user, "post": post, "following": following}
    )


# ----------------------------
# Follow endpoints & Artist profile
# ----------------------------
@app.post("/api/follow")
def api_follow(request: Request, artist: str = Form(...)):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Login required"}, status_code=401)
    ok = follow_artist(user, artist)
    return JSONResponse({"status": "ok", "following": ok})

@app.post("/api/unfollow")
def api_unfollow(request: Request, artist: str = Form(...)):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Login required"}, status_code=401)
    ok = unfollow_artist(user, artist)
    return JSONResponse({"status": "ok", "following": not ok})

@app.get("/artist/{artist_name}", response_class=HTMLResponse)
def artist_profile(request: Request, artist_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, image_path, title, artist, price, created_at,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id = posts.id) AS like_count
        FROM posts
        WHERE artist=?
        ORDER BY created_at DESC
        """,
        (artist_name,)
    )
    rows = c.fetchall()
    # Fetch artist bio (match case-insensitive)
    c.execute("SELECT bio FROM users WHERE LOWER(username)=LOWER(?)", (artist_name,))
    r_bio = c.fetchone()
    conn.close()
    posts = []
    for r in rows:
        posts.append({
            "id": r[0],
            "image": r[1],
            "title": r[2],
            "artist": r[3],
            "price": r[4],
            "created_at": r[5],
            "like_count": r[6] or 0,
        })
    user = request.cookies.get("user")
    following = is_following(user, artist_name) if user else False
    return templates.TemplateResponse("artist.html", {"request": request, "user": user, "artist": artist_name, "posts": posts, "following": following, "artist_bio": (r_bio[0] if r_bio else "")})

# ----------------------------
# Create Post Endpoint
# ----------------------------
@app.post("/create_post")
async def create_post(
    request: Request,
    background_tasks: BackgroundTasks,
    image: List[UploadFile] = File(None),
    title: str = Form(""),
    idea_text: str = Form(None),
    price: str = Form(""),
    contact: str = Form(""),
    category: str = Form("")
):
    # Require login via cookie
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Please log in to create a post."}, status_code=401)
    # Handle multiple images
    image_path = None
    images_list = []
    files = image or []
    if files:
        for file in files:
            ext = os.path.splitext(file.filename)[1] or ".jpg"
            fname = f"{uuid.uuid4().hex}{ext}"
            dest = os.path.join(UPLOAD_DIR, fname)
            with open(dest, "wb") as f:
                content = await file.read()
                f.write(content)
            image_url = f"/static/uploads/{fname}"
            images_list.append(image_url)
        
        # Use first image as primary for backward compatibility
        image_path = images_list[0] if images_list else None

    # Call AI provider in background
    def generate_and_save():
        full_image_path = os.path.join(os.getcwd(), image_path.lstrip('/')) if image_path else None
        if full_image_path and idea_text:
            story, purpose, artist = ai_provider.generate_from_image_and_text(full_image_path, idea_text)
        elif full_image_path:
            story, purpose, artist = ai_provider.generate_from_image(full_image_path)
        else:
            story, purpose, artist = ai_provider.generate_from_text(idea_text or "")
        # Prefer the logged-in username as artist; fallback to AI value
        artist_name = user or artist or ""
        # If AI failed to return story, fall back to user's prompt so detail page isn't empty
        if not story:
            story = idea_text or ""
        insert_post(image_path, title, idea_text, story, purpose, artist_name, price, contact, category, images_list)

    background_tasks.add_task(generate_and_save)
    return JSONResponse({"status": "ok", "message": "Post submitted. Story will be generated shortly."})

# ----------------------------
# Feed API
# ----------------------------
@app.get("/feed_api")
def feed_api(request: Request, following: int = 0, category: str = ""):
    user = request.cookies.get("user")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Build the base query with like_count as a subquery
    base_query = (
        "SELECT id, image_path, title, artist, price, category, created_at, "
        "(SELECT COUNT(*) FROM likes l WHERE l.post_id = posts.id) AS like_count "
        "FROM posts"
    )
    where_conditions = []
    params = []
    
    if following:
        if not user:
            conn.close()
            return JSONResponse({"error": "login required"}, status_code=401)
        where_conditions.append("LOWER(TRIM(artist)) IN (SELECT artist FROM follows WHERE follower=?)")
        params.append(user.lower())
    
    if category:
        where_conditions.append("category = ?")
        params.append(category)
    
    if where_conditions:
        query = f"{base_query} WHERE {' AND '.join(where_conditions)} ORDER BY created_at DESC"
    else:
        query = f"{base_query} ORDER BY created_at DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    posts = []
    for r in rows:
        posts.append({
            "id": r[0],
            "image": r[1],
            "title": r[2],
            "artist": r[3],
            "price": r[4],
            "category": r[5],
            "created_at": r[6],
            "like_count": r[7] or 0,
        })
    return JSONResponse(posts)

# ----------------------------
# Likes: APIs and page
# ----------------------------
@app.post("/api/like")
def api_like(request: Request, post_id: int = Form(...)):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Login required"}, status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO likes (user, post_id) VALUES (?, ?)", (user, post_id))
        conn.commit()
        return JSONResponse({"status": "ok", "liked": True})
    finally:
        conn.close()

@app.post("/api/unlike")
def api_unlike(request: Request, post_id: int = Form(...)):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"status": "error", "message": "Login required"}, status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM likes WHERE user=? AND post_id=?", (user, post_id))
        conn.commit()
        return JSONResponse({"status": "ok", "liked": False})
    finally:
        conn.close()

@app.get("/api/my_liked_ids")
def api_my_liked_ids(request: Request):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT post_id FROM likes WHERE user=?", (user,))
    ids = [r[0] for r in c.fetchall()]
    conn.close()
    return JSONResponse(ids)

@app.get("/api/my_likes")
def api_my_likes(request: Request):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT p.id, p.image_path, p.title, p.artist, p.price, p.category, p.created_at,
               (SELECT COUNT(*) FROM likes l2 WHERE l2.post_id = p.id) AS like_count
        FROM posts p
        JOIN likes l ON l.post_id = p.id
        WHERE l.user = ?
        ORDER BY l.created_at DESC
        """,
        (user,)
    )
    rows = c.fetchall()
    conn.close()
    posts = []
    for r in rows:
        posts.append({
            "id": r[0],
            "image": r[1],
            "title": r[2],
            "artist": r[3],
            "price": r[4],
            "category": r[5],
            "created_at": r[6],
            "like_count": r[7] or 0,
        })
    return JSONResponse(posts)

@app.get("/my_likes", response_class=HTMLResponse)
def my_likes_page(request: Request):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("mylikes.html", {"request": request, "user": user})

# ----------------------------
# Chat APIs (mutual-follow only)
# ----------------------------
@app.get("/api/chat/contacts")
def chat_contacts(request: Request):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # mutual follows: X such that user follows X and X follows user
    c.execute(
        """
        SELECT f1.artist AS contact
        FROM follows f1
        JOIN follows f2 ON LOWER(f2.follower) = LOWER(f1.artist) AND LOWER(f2.artist) = LOWER(f1.follower)
        WHERE LOWER(f1.follower) = LOWER(?)
        ORDER BY contact COLLATE NOCASE
        """,
        (user,),
    )
    contacts = [r[0] for r in c.fetchall()]
    conn.close()
    return JSONResponse(contacts)

@app.get("/api/chat/messages")
def chat_messages(request: Request, with_user: str, limit: int = 50):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    if not is_mutual_follow(user, with_user):
        return JSONResponse({"error": "not allowed"}, status_code=403)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, sender, receiver, content, created_at
        FROM messages
        WHERE (LOWER(sender)=LOWER(?) AND LOWER(receiver)=LOWER(?))
           OR (LOWER(sender)=LOWER(?) AND LOWER(receiver)=LOWER(?))
        ORDER BY created_at ASC, id ASC
        LIMIT ?
        """,
        (user, with_user, with_user, user, limit),
    )
    rows = c.fetchall()
    conn.close()
    messages = [
        {"id": r[0], "sender": r[1], "receiver": r[2], "content": r[3], "created_at": r[4]}
        for r in rows
    ]
    return JSONResponse(messages)

@app.post("/api/chat/send")
def chat_send(request: Request, to: str = Form(...), content: str = Form(...)):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    if not content.strip():
        return JSONResponse({"error": "empty"}, status_code=400)
    if not is_mutual_follow(user, to):
        return JSONResponse({"error": "not allowed"}, status_code=403)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (sender, receiver, content, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (user, to, content.strip()),
    )
    conn.commit()
    msg_id = c.lastrowid
    conn.close()
    return JSONResponse({"ok": True, "id": msg_id})

# ----------------------------
# Debug endpoint: latest post including story
# ----------------------------
@app.get("/debug_latest")
def debug_latest():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, image_path, title, idea_text, story, purpose, artist, price, contact, created_at FROM posts ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "no posts yet"}, status_code=404)
    return JSONResponse({
        "id": row[0],
        "image": row[1],
        "title": row[2],
        "idea_text": row[3],
        "story": row[4],
        "purpose": row[5],
        "artist": row[6],
        "price": row[7],
        "contact": row[8],
        "created_at": row[9]
    })

# ----------------------------
# Signup / Login Routes
# ----------------------------
@app.get("/signup", response_class=HTMLResponse)
def signup_get(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
def signup_post(username: str = Form(...), email: str = Form(...), password: str = Form(...), phone: str = Form(""), bio: str = Form("")):
    password_hash = pwd_context.hash(password)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, email, password_hash, phone, bio) VALUES (?, ?, ?, ?, ?)",
                  (username, email, password_hash, phone, bio))
        conn.commit()
        conn.close()
        return RedirectResponse(url="/login", status_code=303)
    except sqlite3.IntegrityError:
        return HTMLResponse("Username or email already exists. Go back and try again.")

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_post(username: str = Form(...), password: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and pwd_context.verify(password, row[0]):
        resp = RedirectResponse(url="/", status_code=303)
        # Set a simple cookie with the username (demo only; consider secure sessions for production)
        resp.set_cookie(key="user", value=username, httponly=True, samesite="lax")
        return resp
    return HTMLResponse("Invalid username or password. Go back and try again.")

# ----------------------------
# Profile & Following
# ----------------------------
@app.get("/profile", response_class=HTMLResponse)
def profile_get(request: Request):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username, email, phone, bio FROM users WHERE username=?", (user,))
    row = c.fetchone()
    conn.close()
    if not row:
        return HTMLResponse("User not found", status_code=404)
    return templates.TemplateResponse("profile.html", {"request": request, "user": row[0], "email": row[1], "phone": row[2] or "", "bio": row[3] or ""})

@app.post("/profile")
def profile_post(request: Request, email: str = Form(...), phone: str = Form(""), bio: str = Form(""), password: str = Form("")):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if password:
        password_hash = pwd_context.hash(password)
        c.execute("UPDATE users SET email=?, phone=?, bio=?, password_hash=? WHERE username=?", (email, phone, bio, password_hash, user))
    else:
        c.execute("UPDATE users SET email=?, phone=?, bio=? WHERE username=?", (email, phone, bio, user))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/profile", status_code=303)

@app.get("/following", response_class=HTMLResponse)
def following_get(request: Request):
    user = request.cookies.get("user")
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT artist FROM follows WHERE follower=? ORDER BY artist ASC", (user.lower(),))
    artists = [r[0] for r in c.fetchall()]
    # Get bios for followed artists
    bios = {}
    if artists:
        placeholders = ",".join(["?"] * len(artists))
        c = sqlite3.connect(DB_PATH).cursor()
        c.execute(f"SELECT username, bio FROM users WHERE LOWER(username) IN ({placeholders})", [a for a in artists])
        for name, bio in c.fetchall():
            bios[name.lower()] = bio or ""
    enriched = [{"name": a, "bio": bios.get(a, bios.get(a.lower(), ""))} for a in artists]
    conn.close()
    return templates.TemplateResponse("following.html", {"request": request, "user": user, "artists": enriched})

# ----------------------------
# Logout
# ----------------------------
@app.get("/logout")
def logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user")
    return resp

@app.get("/api/my_posts")
def get_my_posts(request: Request):
    user = request.cookies.get("user")
    if not user:
        return JSONResponse({"error": "login required"}, status_code=401)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, image_path, title, artist, price, category, created_at,
               (SELECT COUNT(*) FROM likes l WHERE l.post_id = posts.id) AS like_count
        FROM posts
        WHERE artist=?
        ORDER BY created_at DESC
        """,
        (user,)
    )
    rows = c.fetchall()
    conn.close()
    
    posts = []
    for r in rows:
        posts.append({
            "id": r[0],
            "image": r[1],
            "title": r[2],
            "artist": r[3],
            "price": r[4],
            "category": r[5],
            "created_at": r[6],
            "like_count": r[7] or 0,
        })
    return JSONResponse(posts)

@app.post("/generate_art_api")
async def generate_art_api(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "").strip()
    model = (data.get("model") or "turbo").strip()
    # Disallow 'turbo' model; coerce to a preferred default
    if model.lower() == "turbo":
        model = "flux"
    if not prompt:
        return JSONResponse({"status": "error", "message": "Prompt required."}, status_code=400)

    # Call SubNP Free API (SSE streaming) and collect final image URL
    api_url = "https://subnp.com/api/free/generate"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            # Send POST with prompt and model
            artistic_guardrails = (
                "Create an artistic, stylized, non-photorealistic image. "
                "Avoid realism and photographic rendering. Favor illustration, painting, watercolor, "
                "digital art, brush strokes, stylized textures, and artistic composition. "
                "No photo-realism."
            )
            effective_prompt = f"{artistic_guardrails}\n\nSubject: {prompt}"
            resp = await client.post(api_url, json={"prompt": effective_prompt, "model": model})
            # Expect an SSE stream in the body
            image_url = None
            error_message = None
            async for line in resp.aiter_lines():
                if not line:
                    continue
                # SSE lines we care about begin with 'data: '
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    status = payload.get("status")
                    if status == "complete":
                        image_url = payload.get("imageUrl") or payload.get("image_url")
                        break
                    elif status == "error":
                        error_message = payload.get("message") or "Generation failed"
                        break
            if error_message:
                return JSONResponse({"status": "error", "message": error_message}, status_code=502)
            if not image_url:
                return JSONResponse({"status": "error", "message": "No image returned by provider."}, status_code=502)
            # Optionally create a short summary from the prompt
            summary = (
                f"Artistic (non-realistic) render with {model}: {prompt[:120]}" 
                + ("..." if len(prompt) > 120 else "")
            )
            return JSONResponse({
                "status": "ok",
                "image": image_url,
                "summary": summary
            })
    except httpx.HTTPError as e:
        return JSONResponse({"status": "error", "message": f"Upstream error: {str(e)}"}, status_code=502)

@app.get("/free_models")
async def free_models():
    """Proxy SubNP free models list to avoid CORS issues in the browser."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://subnp.com/api/free/models")
            r.raise_for_status()
            data = r.json()
            # Normalize to a simple list if needed
            models = data.get("models") if isinstance(data, dict) else data
            # Filter out 'turbo' entries entirely
            filtered = []
            for m in (models or []):
                name = (m.get("model") if isinstance(m, dict) else str(m))
                provider = (m.get("provider") if isinstance(m, dict) else "")
                if name and name.lower() == "turbo":
                    continue
                filtered.append(m)
            return JSONResponse({"success": True, "models": filtered})
    except httpx.HTTPError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=502)
