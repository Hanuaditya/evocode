import urllib.request
import urllib.error
import json
import time

url = 'http://127.0.0.1:8000/api/report'
data = json.dumps({
    'bug_text': 'Add a 4th square box right next to or below Languages, Education, and Projects for "Achievements". Inside this box, add the text: "Hackfest-26 2nd runner up 36 hr national level hackathon with 30000 cash prize". Make sure it uses the exact same styling and Tailwind classes as the other boxes.',
    'file_path': 'app/components/About.jsx'
}).encode('utf-8')

headers = {'Content-Type': 'application/json'}
req = urllib.request.Request(url, data=data, headers=headers)

try:
    print("Submitting to API...")
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        issue_id = result.get('issue_id')
        print(f'Submitted issue: {issue_id}')
        
    for i in range(15):
        time.sleep(3)
        status_req = urllib.request.Request(f'http://127.0.0.1:8000/api/status/{issue_id}')
        with urllib.request.urlopen(status_req) as s_response:
            status_result = json.loads(s_response.read().decode())
            print(f'Status: {status_result}')
            if status_result.get('status') == 'completed':
                print(f'\nSUCCESS! PR URL: {status_result.get("pr_url")}')
                break
            elif status_result.get('status') == 'failed':
                print('\nFAILED!')
                break
except Exception as e:
    print(f'Error: {e}')
