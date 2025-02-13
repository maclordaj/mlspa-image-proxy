# MLS Image Proxy Service

A lightweight, production-ready image proxy service that caches MLS listing images using Cloudflare R2 storage.

## Features

- Serves images from Cloudflare R2 storage
- Automatically fetches and caches images from MLS source
- Input validation and sanitization
- Proper error handling and logging
- Cache-Control headers for optimal performance

## Prerequisites

- Python 3.8+
- Cloudflare R2 account and credentials
- Nginx or Apache web server

## Installation

1. Clone the repository:
```bash
git clone [your-repo-url]
cd mlspa-image-proxy
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your Cloudflare R2 credentials:
```
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
```

## Running the Service

### Development
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Production with Nginx

1. Create a systemd service file `/etc/systemd/system/mlspa-proxy.service`:
```ini
[Unit]
Description=MLSPA Image Proxy
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/mlspa-image-proxy
Environment="PATH=/path/to/mlspa-image-proxy/venv/bin"
ExecStart=/path/to/mlspa-image-proxy/venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
```

2. Configure Nginx (create `/etc/nginx/sites-available/mlspa-proxy`):
```nginx
server {
    listen 80;
    server_name int.clientsite.com;

    location /mls-images/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 10M;
    }
}
```

3. Enable and start the services:
```bash
sudo ln -s /etc/nginx/sites-available/mlspa-proxy /etc/nginx/sites-enabled/
sudo systemctl start mlspa-proxy
sudo systemctl enable mlspa-proxy
sudo systemctl restart nginx
```

### Production with Apache

1. Create the same systemd service as above.

2. Configure Apache (create `/etc/apache2/sites-available/mlspa-proxy.conf`):
```apache
<VirtualHost *:80>
    ServerName int.clientsite.com
    
    ProxyPreserveHost On
    ProxyPass /mls-images/ http://127.0.0.1:8000/
    ProxyPassReverse /mls-images/ http://127.0.0.1:8000/
    
    ErrorLog ${APACHE_LOG_DIR}/mlspa-proxy-error.log
    CustomLog ${APACHE_LOG_DIR}/mlspa-proxy-access.log combined
</VirtualHost>
```

3. Enable required modules and site:
```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2ensite mlspa-proxy
sudo systemctl restart apache2
```

## Usage

Access images via: `https://int.clientsite.com/mls-images/<image_name>`

## Error Handling

- 400: Bad Request (invalid image name)
- 404: Image not found
- 500: Internal server error

## Monitoring

Check the application logs:
```bash
sudo journalctl -u mlspa-proxy -f
```
