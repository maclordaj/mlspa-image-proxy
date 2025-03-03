# MLS Image Proxy Service

A production-ready system for serving and caching MLS listing images, consisting of:
1. FastAPI proxy service with Cloudflare R2 storage
2. Symfony MLS integration for data synchronization

## Prerequisites

- Python 3.8+
- PHP 7.2+
- Cloudflare R2 account
- Apache web server
- MLS API access

## Configuration

### 1. Environment Setup

Create a `.env` file with your Cloudflare R2 credentials:
```
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
```

### 2. FastAPI Proxy Installation

```bash
# Clone and setup
git clone [your-repo-url]
cd mlspa-image-proxy
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create service
sudo tee /etc/systemd/system/mlspa-proxy.service << EOF
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
EOF

# Start service
sudo systemctl enable mlspa-proxy
sudo systemctl start mlspa-proxy
```

### 3. Apache Configuration

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

```bash
sudo a2enmod proxy proxy_http
sudo a2ensite mlspa-proxy
sudo systemctl restart apache2
```

### 4. Symfony Integration

1. Update Symfony parameters:
```yaml
# app/config/parameters.yml
parameters:
    int_photos_baseurl: 'https://int.clientsite.com/mls-images/'
```

2. Configure MLS directories:
```bash
# Create temp directory for MLS files
mkdir -p /tmp/$(date +%Y%m%d)/mls-photos
chmod 755 /tmp/$(date +%Y%m%d)/mls-photos
```

## Usage

### Running MLS Integration

```bash
# Full sync
/var/www/symfony/bin/console integration-force-mls:execute -vv -e prod

# Photos only sync
/var/www/symfony/bin/console integration-force-mls:execute -vv -e prod \
    --enable-photos-missing \
    --disable-agents \
    --disable-office \
    --disable-residential \
    --disable-commercial \
    --disable-inactive
```

### Accessing Images

- Format: `https://int.clientsite.com/mls-images/<image_name>`
- Example: `https://int.clientsite.com/mls-images/12345678.L01.jpg`

## System Flow

1. MLS Integration Process:
   - Symfony downloads MLS data
   - Creates photo records in Salesforce
   - Generates photo URLs using proxy domain

2. Image Serving Process:
   - Client requests image from proxy
   - Proxy checks R2 cache
   - If not cached, downloads from MLS
   - Serves image and caches in R2

## Monitoring

### Logs
- FastAPI Proxy: `sudo journalctl -u mlspa-proxy -f`
- Symfony: `/var/log/symfony/prod.log`
- Apache: `/var/log/apache2/mlspa-proxy-error.log`

### Common Issues

1. Missing Photos
   - Check temp directory permissions
   - Verify R2 connectivity
   - Validate MLS API access

2. Integration Errors
   - Review Symfony logs
   - Check Salesforce API limits
   - Verify MLS credentials
