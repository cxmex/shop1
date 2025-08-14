import io
import os
from PIL import Image
from supabase import create_client, Client

# --- CONFIG ---
SUPABASE_URL = "https://gbkhkbfbarsnpbdkxzii.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdia2hrYmZiYXJzbnBiZGt4emlpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzQzODAzNzMsImV4cCI6MjA0OTk1NjM3M30.mcOcC2GVEu_wD3xNBzSCC3MwDck3CIdmz4D8adU-bpI"
BUCKET_NAME = "image-fundas"  # Replace with your Supabase storage bucket name
WEBP_QUALITY = 70
MAX_SIZE = 400  # Max width/height for mobile optimization

# --- CONNECT TO SUPABASE ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ensure new columns exist in the table (will do nothing if they already exist)
def ensure_columns():
    try:
        supabase.rpc("alter_table_add_column", {
            "table_name": "image_uploads",
            "column_name": "file_path_webp",
            "data_type": "text"
        }).execute()
    except Exception:
        pass
    try:
        supabase.rpc("alter_table_add_column", {
            "table_name": "image_uploads",
            "column_name": "public_url_webp",
            "data_type": "text"
        }).execute()
    except Exception:
        pass

# Convert image to WebP (resizing to MAX_SIZE)
def convert_to_webp(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((MAX_SIZE, MAX_SIZE))  # Resize
    webp_io = io.BytesIO()
    img.save(webp_io, format="WEBP", quality=WEBP_QUALITY)
    webp_io.seek(0)
    return webp_io

# Process images
def process_images():
    # Get images without webp versions
    rows = supabase.table("image_uploads") \
        .select("id, file_path, public_url, file_path_webp, public_url_webp") \
        .execute().data

    for row in rows:
        if row["file_path_webp"] and row["public_url_webp"]:
            continue  # Already processed

        print(f"Processing {row['file_path']}...")

        # Download original image from public_url
        import requests
        resp = requests.get(row["public_url"])
        if resp.status_code != 200:
            print(f"❌ Failed to download {row['public_url']}")
            continue

        # Convert to WebP
        webp_io = convert_to_webp(resp.content)

        # Define new file path
        base_name = os.path.splitext(os.path.basename(row["file_path"]))[0]
        webp_filename = f"{base_name}.webp"
        webp_path = f"webp/{webp_filename}"  # Put in 'webp/' folder in storage

        # Upload to Supabase storage
        supabase.storage.from_(BUCKET_NAME).upload(webp_path, webp_io.read(), {
            "content-type": "image/webp"
        })

        # Get public URL for WebP
        webp_url = supabase.storage.from_(BUCKET_NAME).get_public_url(webp_path)

        # Update row in DB
        supabase.table("image_uploads").update({
            "file_path_webp": webp_path,
            "public_url_webp": webp_url
        }).eq("id", row["id"]).execute()

        print(f"✅ Created WebP: {webp_url}")

if __name__ == "__main__":
    ensure_columns()
    process_images()
