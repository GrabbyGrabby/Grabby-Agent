import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cloudflare_dns")

def get_public_ip():
    """Retrieve the public IP address of the local machine."""
    urls = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/all.json",
        "https://ipinfo.io/json"
    ]
    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "ip" in data:
                    return data["ip"]
                elif "ip_addr" in data:
                    return data["ip_addr"]
        except Exception as e:
            logger.warning(f"Failed to fetch IP from {url}: {e}")
    
    # Fallback to plain text ipify if JSON endpoints fail
    try:
        return requests.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception as e:
        logger.error(f"Failed to determine public IP address: {e}")
        return None

def sync_cloudflare_dns():
    """Sync the public IP with Cloudflare DNS record."""
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
    domain = os.getenv("CLOUDFLARE_DOMAIN")
    auto_sync = os.getenv("CLOUDFLARE_AUTO_SYNC", "true").lower() == "true"

    if not auto_sync:
        logger.info("Cloudflare DNS auto-sync is disabled in configuration.")
        return False

    if not token or not zone_id or not domain:
        logger.warning("Cloudflare DNS variables (CLOUDFLARE_API_TOKEN, CLOUDFLARE_ZONE_ID, CLOUDFLARE_DOMAIN) not fully set. Skipping DNS sync.")
        return False

    public_ip = get_public_ip()
    if not public_ip:
        logger.error("Could not obtain public IP. DNS update skipped.")
        return False

    logger.info(f"Targeting Domain: {domain} -> Public IP: {public_ip}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Search for existing DNS record
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    params = {"name": domain, "type": "A"}

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            logger.error(f"Cloudflare API error listing records: {res.text}")
            return False
        
        records = res.json().get("result", [])
        
        record_data = {
            "type": "A",
            "name": domain,
            "content": public_ip,
            "ttl": 1,  # Automatic TTL
            "proxied": True  # Cloudflare proxy enabled (hides server IP, adds SSL)
        }

        if records:
            # Update existing record
            record_id = records[0]["id"]
            current_ip = records[0]["content"]
            
            if current_ip == public_ip:
                logger.info(f"Cloudflare DNS record is already up-to-date ({domain} -> {public_ip}).")
                return True
                
            update_url = f"{url}/{record_id}"
            put_res = requests.put(update_url, headers=headers, json=record_data, timeout=10)
            if put_res.status_code == 200:
                logger.info(f"Successfully updated Cloudflare DNS record for {domain} to {public_ip}.")
                return True
            else:
                logger.error(f"Failed to update Cloudflare DNS record: {put_res.text}")
                return False
        else:
            # Create new record
            post_res = requests.post(url, headers=headers, json=record_data, timeout=10)
            if post_res.status_code == 200:
                logger.info(f"Successfully created new Cloudflare DNS record: {domain} -> {public_ip}.")
                return True
            else:
                logger.error(f"Failed to create Cloudflare DNS record: {post_res.text}")
                return False

    except Exception as e:
        logger.error(f"Exception during Cloudflare DNS sync: {e}")
        return False

if __name__ == "__main__":
    sync_cloudflare_dns()
