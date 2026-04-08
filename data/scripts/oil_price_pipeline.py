# Step 1: Import HTTP library
import requests

# Step 2: Define test API endpoint (placeholder before real oil price API)
API_URL = "https://jsonplaceholder.typicode.com/todos/1"


# Step 3: Fetch data from the API and return parsed JSON
def fetch_data():
    # Step 4: Send GET request to the API
    response = requests.get(API_URL)
    # Step 5: Raise an error if the request failed (non-2xx status)
    response.raise_for_status()
    return response.json()


# Step 6: Define main pipeline function
def main():
    # Step 7: Call the API and print the response
    data = fetch_data()
    print("API response:", data)


# Step 8: Entry point guard
if __name__ == "__main__":
    main()
