"""
Mappedin API Module
Handles authentication and data retrieval from the Mappedin REST API
"""

import json
import tempfile
import os
import time
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    raise ImportError(
        "The 'requests' library is required for API functionality. "
        "This library is typically included with QGIS installations. "
        "If you encounter this error, please install the requests library or use the file import option instead."
    )


class MappedInAPIClient:
    """
    Client for interacting with the Mappedin REST API to fetch MVF v3 packages.
    
    Based on the Mappedin API documentation:
    https://developer.mappedin.com/docs/mvf/v3/getting-started#downloading-an-mvf-using-the-mappedin-rest-api
    """
    
    def __init__(self):
        """Initialize the API client"""
        self.api_base_url = "https://app.mappedin.com/api/v1"
        self.jwt_token = None
        self.token_expires_in = None
        # Store credentials for token caching
        self._api_key = None
        self._api_secret = None
        self._token_issued_time = None
        # Conservative expiry assumption (2 hours = 7200 seconds)
        self._assumed_token_lifetime = 7200
        
    def authenticate(self, api_key: str, api_secret: str) -> Tuple[bool, str]:
        """
        Exchange API key and secret for JWT token
        
        Args:
            api_key (str): Mappedin API key (starts with 'mik_')
            api_secret (str): Mappedin API secret (starts with 'mis_')
            
        Returns:
            Tuple[bool, str]: (success, error_message_if_failed)
        """
        try:
            # Validate input format
            if not api_key.startswith('mik_'):
                return False, "API key should start with 'mik_'"
            
            if not api_secret.startswith('mis_'):
                return False, "API secret should start with 'mis_'"
            
            # Prepare authentication request
            auth_url = f"{self.api_base_url}/api-key/token"
            payload = {
                "key": api_key,
                "secret": api_secret
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Make authentication request
            response = requests.post(
                auth_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                auth_data = response.json()
                new_token = auth_data.get('access_token')
                self.token_expires_in = auth_data.get('expires_in', 172800)  # Default 48 hours
                
                if new_token:
                    # Check if we got the same expired token back
                    if hasattr(self, '_last_rejected_token') and new_token == self._last_rejected_token:
                        # DEBUG: print(f"Mappedin returned the same expired token - credentials may be tied to expired token")
                        return False, "Mappedin returned the same expired token. Please try with different credentials or wait a few minutes."
                    
                    self.jwt_token = new_token
                    # Store credentials and token time for auto-refresh
                    self._api_key = api_key
                    self._api_secret = api_secret
                    self._token_issued_time = time.time()
                    
                    # DEBUG: print(f"Token obtained successfully (Mappedin says valid for {self.token_expires_in/3600:.1f}h, assuming 2h for safety)")
                    # DEBUG: print(f"Token preview: {self.jwt_token[:50]}...")
                    
                    # Brief delay to ensure token is active on Mappedin's side
                    time.sleep(0.5)
                    # DEBUG: print("Token activation delay complete")
                    return True, ""
                else:
                    return False, "No access token in response"
            
            elif response.status_code == 401:
                return False, "Invalid API key or secret"
            elif response.status_code == 403:
                return False, "API access forbidden - check your account permissions"
            elif response.status_code == 429:
                return False, "Rate limit exceeded - please try again later"
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                return False, f"Authentication failed: {error_msg}"
                
        except requests.exceptions.Timeout:
            return False, "Request timeout - please check your internet connection"
        except requests.exceptions.ConnectionError:
            return False, "Connection error - please check your internet connection"
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error during authentication: {str(e)}"
    

    def _is_cached_token_valid(self) -> bool:
        """Check if our cached token is still valid (conservative 2-hour assumption)"""
        if not self.jwt_token or not self._token_issued_time:
            return False
        
        current_time = time.time()
        token_age = current_time - self._token_issued_time
        
        # Use conservative 2-hour assumption with 5-minute safety buffer
        safe_lifetime = self._assumed_token_lifetime - 300  # 2h - 5min = 115 minutes
        is_valid = token_age < safe_lifetime
        
        if not is_valid:
            # DEBUG: print(f"Cached token expired: age={token_age/60:.1f}min, limit={safe_lifetime/60:.1f}min")
        
        return is_valid
    

    
    def _auto_refresh_token(self) -> bool:
        """Automatically refresh the token using stored credentials"""
        if not self._api_key or not self._api_secret:
            # DEBUG: print("Cannot auto-refresh: No stored credentials")
            return False
        
        # Prevent refresh loops - don't refresh if we just did within last 30 seconds
        current_time = time.time()
        if hasattr(self, '_last_refresh_time'):
            time_since_refresh = current_time - self._last_refresh_time
            if time_since_refresh < 30:
                # DEBUG: print(f"Skipping refresh - too recent (last {time_since_refresh:.1f}s ago)")
                return True
        
        # DEBUG: print("Auto-refreshing token...")
        self._last_refresh_time = current_time
        success, error = self.authenticate(self._api_key, self._api_secret)
        if success:
            # DEBUG: print("Token refreshed successfully")
        else:
            print(f"Token refresh failed: {error}")
        return success
    

    
    def get_token_cache_status(self) -> str:
        """Get human-readable token cache status"""
        if not self.jwt_token:
            return "No token cached"
        if not self._token_issued_time:
            return "Token cached but missing timestamp"
        
        current_time = time.time()
        token_age = current_time - self._token_issued_time
        safe_lifetime = self._assumed_token_lifetime - 300
        time_remaining = safe_lifetime - token_age
        
        if time_remaining > 0:
            return f"Token valid (age: {token_age/60:.1f}min, {time_remaining/60:.1f}min remaining)"
        else:
            return f"Token expired (age: {token_age/60:.1f}min, expired {abs(time_remaining)/60:.1f}min ago)"
    
    def _make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make an authenticated request with token caching and 401 retry"""
        # Ensure we have a token (don't pre-check expiry, let Mappedin tell us if it's expired)
        if not self.jwt_token:
            if self._api_key and self._api_secret:
                # DEBUG: print("No token, authenticating...")
                success, error = self.authenticate(self._api_key, self._api_secret)
                if not success:
                    raise Exception(f"Authentication failed: {error}")
            else:
                raise Exception("No token and no stored credentials")
        
        # Add auth header
        headers = kwargs.get('headers', {})
        auth_header = f"Bearer {self.jwt_token}"
        headers['Authorization'] = auth_header
        kwargs['headers'] = headers
        
        # DEBUG: print(f"Making {method} request to {url}")
        # DEBUG: print(f"Auth header: Bearer {self.jwt_token[:20]}...{self.jwt_token[-10:]}")
        
        # Make the request
        response = getattr(requests, method.lower())(url, **kwargs)
        
        # If Mappedin says token is expired (401), invalidate cache and retry ONCE
        if response.status_code == 401:
            # DEBUG: print(f"Mappedin rejected token (401) for {method} {url}")
            try:
                error_details = response.json()
                print(f"  Error details: {error_details}")
            except:
                # DEBUG: print(f"  Response text: {response.text}")
            # DEBUG: print(f"  Request headers: {kwargs.get('headers', {})}")
            
            # Store the rejected token so we can detect if Mappedin gives us the same one back
            self._last_rejected_token = self.jwt_token
            # Invalidate our cache since Mappedin says it's expired
            self._token_issued_time = None
            
            # Check if we haven't refreshed very recently to avoid loops
            current_time = time.time()
            can_retry = True
            if hasattr(self, '_last_refresh_time'):
                time_since_refresh = current_time - self._last_refresh_time
                if time_since_refresh < 10:  # Don't retry if refreshed within 10 seconds
                    can_retry = False
                    print(f"401 error but not retrying - recent refresh ({time_since_refresh:.1f}s ago)")
            
            if can_retry and self._auto_refresh_token():
                # DEBUG: print("Got fresh token, retrying request...")
                headers['Authorization'] = f"Bearer {self.jwt_token}"
                kwargs['headers'] = headers
                response = getattr(requests, method.lower())(url, **kwargs)
                if response.status_code == 401:
                    # DEBUG: print("Still getting 401 after fresh token - authentication issue")
        
        return response
    
    def get_venues_list(self) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """
        Get list of available venues for the authenticated user
        
        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (success, error_or_message, venues_list)
        """
        try:
            # Get venues list using the correct Mappedin API endpoint
            # Based on https://docs.mappedin.com/mappedin-rest-api/#tag/venue/get/v1/venue
            venues_url = f"{self.api_base_url}/venue"
            
            # Add query parameters as specified in the API documentation
            # Note: boolean values need to be lowercase strings for the API
            params = {
                "limit": 100,
                "visibility": "public", 
                "include_archived": "false"
            }
            
            response = self._make_authenticated_request(
                "GET",
                venues_url,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                venues_data = response.json()
                
                # Handle different response formats
                if isinstance(venues_data, list):
                    venues_list = venues_data
                elif isinstance(venues_data, dict):
                    # The API likely returns data in a structured format
                    venues_list = venues_data.get('venues', venues_data.get('data', venues_data.get('results', [])))
                    
                    # Some APIs return the list directly under the main object
                    if not venues_list and 'items' in venues_data:
                        venues_list = venues_data['items']
                    
                    # Debug: if we still don't have venues, let's see what keys are available
                    if not venues_list:
                        available_keys = list(venues_data.keys()) if venues_data else []
                        return False, f"No venues found in response. Available keys: {available_keys}. Response type: {type(venues_data)}", None
                else:
                    venues_list = []
                
                return True, "Success", venues_list
            
            elif response.status_code == 401:
                return False, "Authentication failed after retry", None
            elif response.status_code == 403:
                return False, "Access forbidden - check account permissions", None
            elif response.status_code == 404:
                return False, "Venue endpoint not found - check your account has API access", None
            elif response.status_code == 429:
                return False, "Rate limit exceeded - please try again later", None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', error_data.get('error', f'HTTP {response.status_code}'))
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                return False, f"API request failed: {error_msg}", None
                
        except requests.exceptions.Timeout:
            return False, "Request timeout - please check your internet connection", None
        except requests.exceptions.ConnectionError:
            return False, "Connection error - please check your internet connection", None
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error getting venues list: {str(e)}", None

    def get_mvf_download_url(self, venue_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Get MVF v3 download URL for a specific venue
        
        Args:
            venue_id (str): The venue/map ID to download
            
        Returns:
            Tuple[bool, str, Optional[Dict]]: (success, error_or_url, metadata)
        """
        try:
            # Get MVF download link
            mvf_url = f"{self.api_base_url}/venue/{venue_id}/mvf?version=3.0.0"
            
            # For GET requests, we only need the Authorization header (added by _make_authenticated_request)
            response = self._make_authenticated_request(
                "GET",
                mvf_url,
                timeout=30
            )
            
            if response.status_code == 200:
                mvf_data = response.json()
                download_url = mvf_data.get('url')
                
                if download_url:
                    # Include metadata about the download
                    metadata = {
                        'updated_at': mvf_data.get('updated_at'),
                        'locale_packs': mvf_data.get('locale_packs', {}),
                        'venue_id': venue_id
                    }
                    return True, download_url, metadata
                else:
                    return False, "No download URL in response", None
            
            elif response.status_code == 401:
                return False, "Authentication failed after retry", None
            elif response.status_code == 403:
                return False, "Access forbidden - check venue permissions", None
            elif response.status_code == 404:
                return False, f"Venue '{venue_id}' not found or not accessible", None
            elif response.status_code == 429:
                return False, "Rate limit exceeded - please try again later", None
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                return False, f"Failed to get download URL: {error_msg}", None
                
        except requests.exceptions.Timeout:
            return False, "Request timeout - please check your internet connection", None
        except requests.exceptions.ConnectionError:
            return False, "Connection error - please check your internet connection", None
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}", None
        except Exception as e:
            return False, f"Unexpected error getting download URL: {str(e)}", None
    
    def download_mvf_package(self, download_url: str, progress_callback=None) -> Tuple[bool, str, Optional[str]]:
        """
        Download MVF package from the provided URL
        
        Args:
            download_url (str): URL to download the MVF package from
            progress_callback (callable): Optional callback for download progress
            
        Returns:
            Tuple[bool, str, Optional[str]]: (success, error_or_file_path, temp_file_path)
        """
        try:
            # Create temporary file for download
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.zip',
                prefix='mappedin_mvf_'
            )
            temp_file_path = temp_file.name
            temp_file.close()
            
            # Download the file
            response = requests.get(download_url, stream=True, timeout=60)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(temp_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Call progress callback if provided
                            if progress_callback and total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                progress_callback(progress)
                
                # Verify the file was downloaded successfully
                if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                    return True, temp_file_path, temp_file_path
                else:
                    return False, "Downloaded file is empty or invalid", temp_file_path
            
            elif response.status_code == 403:
                return False, "Download URL expired or access forbidden", temp_file_path
            elif response.status_code == 404:
                return False, "Download URL not found or expired", temp_file_path
            else:
                return False, f"Download failed with HTTP {response.status_code}", temp_file_path
                
        except requests.exceptions.Timeout:
            return False, "Download timeout - the file may be too large", temp_file_path
        except requests.exceptions.ConnectionError:
            return False, "Connection error during download", temp_file_path
        except requests.exceptions.RequestException as e:
            return False, f"Download failed: {str(e)}", temp_file_path
        except Exception as e:
            return False, f"Unexpected error during download: {str(e)}", temp_file_path
    
    def fetch_mvf_package(self, api_key: str, api_secret: str, venue_id: str, progress_callback=None) -> Tuple[bool, str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Complete workflow to fetch MVF package from API
        
        Args:
            api_key (str): Mappedin API key
            api_secret (str): Mappedin API secret  
            venue_id (str): Venue ID to download
            progress_callback (callable): Optional progress callback
            
        Returns:
            Tuple[bool, str, Optional[str], Optional[Dict]]: (success, error_or_path, temp_file_path, metadata)
        """
        try:
            # Store credentials for token caching
            self._api_key = api_key
            self._api_secret = api_secret
            
            # Step 1: Ensure we have a valid token (use cache or authenticate fresh)
            if not self._is_cached_token_valid():
                # DEBUG: print("No valid cached token, authenticating with provided credentials...")
                auth_success, auth_error = self.authenticate(api_key, api_secret)
                if not auth_success:
                    return False, f"Authentication failed: {auth_error}", None, None
            else:
                # DEBUG: print("Using cached token for MVF download")
            
            # Step 2: Get download URL
            url_success, url_result, metadata = self.get_mvf_download_url(venue_id)
            if not url_success:
                return False, f"Failed to get download URL: {url_result}", None, None
            
            download_url = url_result
            
            # Step 3: Download the package
            download_success, download_result, temp_file_path = self.download_mvf_package(
                download_url, progress_callback
            )
            
            if download_success:
                return True, download_result, temp_file_path, metadata
            else:
                return False, f"Download failed: {download_result}", temp_file_path, metadata
                
        except Exception as e:
            return False, f"Unexpected error in fetch workflow: {str(e)}", None, None
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """
        Clean up temporary downloaded file
        
        Args:
            temp_file_path (str): Path to temporary file to delete
        """
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception:
            pass  # Ignore cleanup errors
