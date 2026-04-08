import fs from 'fs'
import path from 'path'
const dir = path.join(process.cwd(), 'public/icons')
fs.mkdirSync(dir, { recursive: true })
// 1x1 green PNG
const pngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQAABjE+ibYAAAAASUVORK5CYII='
fs.writeFileSync(path.join(dir, 'icon-192.png'), Buffer.from(pngBase64, 'base64'))
fs.writeFileSync(path.join(dir, 'icon-512.png'), Buffer.from(pngBase64, 'base64'))
console.log('Icons generated.')
