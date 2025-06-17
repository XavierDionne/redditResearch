import datetime
import http.server
import socket
import socketserver
import ssl
import requests
import json
import sqlite3
from urllib.parse import parse_qs, urlparse

# Reddit API credentials (replace with your own)
CLIENT_ID = ""  # Replace with your client_id
CLIENT_SECRET = ""  # Replace with your client_secret
USER_AGENT = 'your_user_agent'

def create_post_hash(post_data):
    """Create a unique hash for a post based on its ID and subreddit"""
    return f"{post_data['id']}_{post_data['subreddit']}"

def timestamp_to_date(timestamp):
    """Convert Unix timestamp to readable date string"""
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

def initialize_db():
    """Initialize the database and create the necessary table"""
    with sqlite3.connect('reddit_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                sort_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                title TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                score INTEGER,
                post_date INTEGER,
                post_hash TEXT UNIQUE NOT NULL,
                timeframe TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def search_reddit(query, subreddits=['python'], timeframe='all', after=None):
    posts_data = []
    last_after = None
    
    for subreddit in subreddits:
        url = f'https://www.reddit.com/r/{subreddit}/search.json?q={query}&limit=100&restrict_sr=true&sort=new'
        if after:
            url += f'&after={after}'
            
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            posts_data.extend(data['data']['children'])
            last_after = data['data'].get('after')
        except Exception as e:
            print(f"Error fetching data from subreddit {subreddit}: {str(e)}")
            continue
    
    posts_data.sort(key=lambda x: x['data']['created_utc'], reverse=True)
    return posts_data, last_after

def save_to_db(posts_data, timeframe):
    """Save post data to database with enhanced information"""
    with sqlite3.connect('reddit_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('BEGIN TRANSACTION')
        
        for post in posts_data:
            post_data = post['data']
            post_hash = create_post_hash(post_data)
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO posts 
                    (post_id, title, subreddit, score, post_date, post_hash, timeframe)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    post_data['id'],
                    post_data['title'],
                    post_data['subreddit'],
                    post_data['score'],
                    post_data['created_utc'],
                    post_hash,
                    timeframe
                ))
            except sqlite3.IntegrityError:
                print(f"Skipping duplicate post: {post_hash}")
        
        conn.commit()
        cursor.execute('SELECT COUNT(*) FROM posts')
        row_count = cursor.fetchone()[0]
        print(f"Total posts in database: {row_count}")

class RedditSearchHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/':
            self.path = 'index.html'
            return super().do_GET()
        elif parsed_path.path == '/search':
            self.handle_search_request(parsed_path.query)
        elif parsed_path.path == '/db_status':
            self.handle_db_status_request()
        else:
            self.path = parsed_path.path
            return super().do_GET()

    def handle_db_status_request(self):
        try:
            with sqlite3.connect('reddit_data.db') as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM posts')
                count = cursor.fetchone()[0]
                cursor.execute('SELECT post_id, title, created_at FROM posts ORDER BY created_at DESC LIMIT 5')
                recent_posts = cursor.fetchall()
            
            status = {
                'total_posts': count,
                'recent_posts': [
                    {'post_id': p[0], 'title': p[1], 'created_at': p[2]} 
                    for p in recent_posts
                ]
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode('utf-8'))
        except Exception as e:
            self.send_error_response(f"Database error: {str(e)}")

    def handle_search_request(self, query_string):
        query_components = parse_qs(query_string)
        query = query_components.get('q', [None])[0]
        subreddit = query_components.get('subreddit', [None])[0]
        timeframe = query_components.get('timeframe', ['all'])[0]
        after = query_components.get('after', [None])[0]
        
        if query:
            try:
                subreddits = [subreddit] if subreddit else ["python"]
                posts, next_after = search_reddit(query, subreddits=subreddits, timeframe=timeframe, after=after)
                save_to_db(posts, timeframe)
                
                response_data = {
                    'posts': [
                        {
                            'id': post['data']['id'],
                            'title': post['data']['title'],
                            'subreddit': post['data']['subreddit'],
                            'score': post['data']['score'],
                            'date': timestamp_to_date(post['data']['created_utc']),
                            'hash': create_post_hash(post['data'])
                        }
                        for post in posts
                    ],
                    'next_after': next_after
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e:
                self.send_error_response(str(e))
        else:
            self.send_error_response("No query parameter provided")

def run(port=8080):
    initialize_db()
    server = socketserver.TCPServer(('0.0.0.0', port), RedditSearchHandler)
    print(f"Serving at http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run()
