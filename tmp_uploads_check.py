import requests
base='http://localhost:8001'
# login local@up.gov
r=requests.post(base+'/api/auth/login', json={'email':'local@up.gov','password':'admin123'})
print('login', r.status_code, r.json())
token=r.json()['data']['access_token']
headers={'Authorization':'Bearer '+token}
# list uploads
r2=requests.get(base+'/api/uploads', headers=headers)
print('list uploads', r2.status_code)
print(r2.text[:1200])
