from PIL import Image
img = Image.open('static/img/favicon_512.png').convert('RGBA')
img.save('static/img/favicon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64)])
print('done')
