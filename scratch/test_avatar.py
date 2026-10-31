import sys
sys.path.insert(0, '.')
from generators.avatar_generator import list_avatars, load_avatar

avs = list_avatars()
print('Available avatars:', len(avs))
for a in avs:
    print(' - name:', repr(a.get('name')), 'display_name:', repr(a.get('display_name')), 'is_default:', a.get('is_default'))

print('\nTesting load_avatar("小曹"):', repr(load_avatar("小曹").get('name')))
print('Testing load_avatar("tsaotsao"):', repr(load_avatar("tsaotsao").get('name')))
print('Testing load_avatar(None):', repr(load_avatar(None).get('name')))
