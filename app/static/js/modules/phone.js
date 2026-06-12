// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Phone Helper
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const PhoneHelper = {
    mask(value) {
        if (value === undefined || value === null) return '';
        let v = value.toString().replace(/\D/g, '');
        if (v.length > 11) v = v.slice(0, 11);
        
        if (v.length > 10) {
            v = v.replace(/^(\d{2})(\d{5})(\d{4}).*/, '($1) $2-$3');
        } else if (v.length > 5) {
            v = v.replace(/^(\d{2})(\d{4})(\d{0,4}).*/, '($1) $2-$3');
        } else if (v.length > 2) {
            v = v.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
        } else if (v.length > 0) {
            v = v.replace(/^(\d*)/, '($1');
        }
        return v;
    },
    init(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.setAttribute('maxlength', '15');
        
        // Format initial value if any
        if (input.value) {
            input.value = this.mask(input.value);
        }
        
        input.addEventListener('input', (e) => {
            e.target.value = this.mask(e.target.value);
        });
    }
};

// Attach to window for global availability
window.PhoneHelper = PhoneHelper;
