# eyecandy — Flask + Postgres (Supabase) App

## Project structure

```
eyecandy/
├── app.py                # Flask backend (all API routes)
├── requirements.txt      # Python dependencies
├── supabase_schema.sql   # Postgres schema + seed data, run in Supabase SQL Editor
├── remove_duplicates.py  # One-off maintenance script
└── templates/
    └── index.html        # Frontend (HTML/CSS/JS)
```

## Local setup

### 1. Create a Supabase project and run the schema
In the Supabase SQL Editor, paste and run `supabase_schema.sql`. This creates all
tables and seeds some demo data.

Seed accounts are inserted with a placeholder password hash (`unset`) and can't
log in as-is — sign up fresh accounts through the app, or set real hashes
manually if you want the seed users to be usable.

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
export DATABASE_URL="postgresql://postgres.xxxx:PASSWORD@aws-0-xx.pooler.supabase.com:6543/postgres"
export SECRET_KEY="some-long-random-string"
```
Use Supabase's **transaction pooler URI on port 6543** (not the direct
connection on port 5432). The app will refuse to start if either variable is
unset.

### 4. Run the app
```bash
python app.py
```
Visit: http://localhost:5000

## Deploying (Vercel)

1. Push this repo to GitHub.
2. Import it into Vercel — it auto-detects Flask from `app.py`.
3. In Vercel's project settings, set `DATABASE_URL` and `SECRET_KEY` as
   environment variables (same values as above).
4. Deploy. Make sure you've already run `supabase_schema.sql` in Supabase
   before the first request hits the app.

## API Routes

### Auth
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/auth/signup` | Create an account (hashes password, creates buyer/seller rows) |
| POST | `/api/auth/login` | Log in with email + password |
| POST | `/api/auth/logout` | Clear session |
| GET | `/api/auth/current-user` | Get the logged-in user, if any |

### Items
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/items` | All items (supports `?search=`, `?gender=`, `?category=`) |
| GET | `/api/items/<id>` | Single item with images, likes, comments |
| POST | `/api/items` | List a new item |

### Boards
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/boards` | All public boards (supports `?user_id=`) |
| POST | `/api/boards` | Create a board |
| DELETE | `/api/boards/<id>` | Delete a wishlist board (CASCADE removes items) |
| GET | `/api/boards/<id>/items` | Items in a board |
| POST | `/api/boards/<id>/items` | Save item to board |

### Orders
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/orders` | All orders (supports `?buyer_id=`) |
| POST | `/api/orders` | Place order + auto-add to closet |
| PATCH | `/api/orders/<id>/status` | Update order status |

### Users
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/users` | All users |
| GET | `/api/users/<id>` | User profile, closet count, wishlist boards |

### Analytics
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/analytics/top-items` | Most liked items |
| GET | `/api/analytics/seller-performance` | Revenue per seller |
| GET | `/api/analytics/wishlist-never-ordered` | Wishlisted but never bought |

### Engagement
| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/items/<id>/like` | Like an item |
| POST | `/api/items/<id>/comment` | Post a comment |
