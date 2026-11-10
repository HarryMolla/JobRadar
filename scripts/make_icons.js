const fs = require('fs');
const zlib = require('zlib');
const path = require('path');

function makePNG(width, height) {
  const rowSize = width * 4 + 1;
  const raw = Buffer.alloc(rowSize * height);
  const cx = width / 2;
  const cy = height / 2;
  const r = width / 2 - 1;

  for (let y = 0; y < height; y++) {
    const rowOffset = y * rowSize;
    raw[rowOffset] = 0; // Filter type 0 (None)
    for (let x = 0; x < width; x++) {
      const pxOffset = rowOffset + 1 + x * 4;
      const dx = x - cx;
      const dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= r) {
        const ring1 = Math.abs(dist - r * 0.7) < Math.max(1, width / 18);
        const ring2 = Math.abs(dist - r * 0.35) < Math.max(1, width / 20);
        const dot = dist <= Math.max(1.5, width / 8);
        const cross = (Math.abs(dx) <= Math.max(0.7, width / 24) || Math.abs(dy) <= Math.max(0.7, width / 24)) && dist <= r * 0.85;

        if (dot || ring1 || ring2 || cross) {
          raw[pxOffset] = 255;
          raw[pxOffset + 1] = 255;
          raw[pxOffset + 2] = 255;
          raw[pxOffset + 3] = 255;
        } else {
          raw[pxOffset] = 37;
          raw[pxOffset + 1] = 99;
          raw[pxOffset + 2] = 235;
          raw[pxOffset + 3] = 255;
        }
      } else {
        raw[pxOffset] = 0;
        raw[pxOffset + 1] = 0;
        raw[pxOffset + 2] = 0;
        raw[pxOffset + 3] = 0;
      }
    }
  }

  function crc32(buf) {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) {
      c ^= buf[i];
      for (let k = 0; k < 8; k++) {
        c = (c >>> 1) ^ (-(c & 1) & 0xedb88320);
      }
    }
    return (c ^ 0xffffffff) >>> 0;
  }

  function chunk(type, data) {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const tag = Buffer.from(type, 'ascii');
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([tag, data])), 0);
    return Buffer.concat([len, tag, data, crc]);
  }

  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;

  const idatData = zlib.deflateSync(raw);
  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', idatData),
    chunk('IEND', Buffer.alloc(0))
  ]);
}

const outDir = path.join(__dirname, '..', 'extension', 'icons');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

[16, 32, 48, 128].forEach(size => {
  const filePath = path.join(outDir, `icon${size}.png`);
  fs.writeFileSync(filePath, makePNG(size, size));
  console.log(`Wrote ${filePath} (${fs.statSync(filePath).size} bytes)`);
});

