path = '/app/config/settings.py'
with open(path, 'r') as f:
    content = f.read()

content = content.replace('\nfrom celery.schedules import crontab\n', '\n')
content = content.replace(
    'from datetime import timedelta\n',
    'from datetime import timedelta\nfrom celery.schedules import crontab\n'
)

with open(path, 'w') as f:
    f.write(content)
print('done')