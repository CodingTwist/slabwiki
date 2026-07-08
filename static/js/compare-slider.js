"use strict";
// Wires each .compare-slider's <input type=range> to the --pos custom
// property its CSS uses to clip-path the "after" image layer.
function initCompareSlider(el) {
    const input = el.querySelector('.compare-slider-input');
    if (!input)
        return;
    input.addEventListener('input', () => {
        el.style.setProperty('--pos', `${input.value}%`);
    });
}
document.querySelectorAll('.compare-slider').forEach(initCompareSlider);
