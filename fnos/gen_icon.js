const { createCanvas } = require('canvas');
const fs = require('fs');

const size = 512;
const canvas = createCanvas(size, size);
const ctx = canvas.getContext('2d');

// 背景 - 深色渐变
const grad = ctx.createLinearGradient(0, 0, size, size);
grad.addColorStop(0, '#0a0a0f');
grad.addColorStop(1, '#1a1a2e');
ctx.fillStyle = grad;
ctx.fillRect(0, 0, size, size);

// 外圈 - 紫色光晕
ctx.beginPath();
ctx.arc(size/2, size/2, 220, 0, Math.PI * 2);
ctx.strokeStyle = 'rgba(108, 92, 231, 0.3)';
ctx.lineWidth = 8;
ctx.stroke();

// 内圈 - 渐变
const grad2 = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, 180);
grad2.addColorStop(0, 'rgba(108, 92, 231, 0.15)');
grad2.addColorStop(1, 'rgba(108, 92, 231, 0)');
ctx.fillStyle = grad2;
ctx.beginPath();
ctx.arc(size/2, size/2, 180, 0, Math.PI * 2);
ctx.fill();

// 音符 - 🎵 风格化
ctx.fillStyle = '#6c5ce7';
ctx.font = 'bold 200px Arial';
ctx.textAlign = 'center';
ctx.textBaseline = 'middle';
ctx.fillText('♪', size/2, size/2 - 10);

// 音符光晕
ctx.shadowColor = '#6c5ce7';
ctx.shadowBlur = 30;
ctx.fillStyle = 'rgba(108, 92, 231, 0.6)';
ctx.fillText('♪', size/2, size/2 - 10);
ctx.shadowBlur = 0;

// 底部文字
ctx.fillStyle = '#a29bfe';
ctx.font = 'bold 28px -apple-system, BlinkMacSystemFont, sans-serif';
ctx.textAlign = 'center';
ctx.fillText('Music Player', size/2, size - 50);

// 保存
const buffer = canvas.toBuffer('image/png');
fs.writeFileSync('/home/ubuntu/music-player-docker/fnos/icon.png', buffer);
console.log('Icon generated: icon.png (512x512)');
