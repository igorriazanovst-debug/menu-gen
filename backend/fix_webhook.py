path = '/app/apps/payments/tests/test_webhook.py'
with open(path, 'r') as f:
    lines = f.readlines()
lines[64] = '    body = b\'{"event": "payment.succeeded"}\'\n'
with open(path, 'w') as f:
    f.writelines(lines)
print('done')
