// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Cart Manager - Atualizado com Adicionais
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const Cart = {
    KEY: 'cart_v2', 
    
    get() { 
        const c = localStorage.getItem(this.KEY); 
        return c ? JSON.parse(c) : { items: [] }; 
    },
    
    save(cart) { 
        localStorage.setItem(this.KEY, JSON.stringify(cart)); 
        this.updateBadge(); 
    },
    
    /**
     * Adiciona um produto ao carrinho.
     * @param {Object} product - O objeto do produto base.
     * @param {string} restaurantId - ID do restaurante.
     * @param {string} restaurantName - Nome do restaurante.
     * @param {Array} extras - Lista de objetos {nome, preco} selecionados no modal.
     */
    add(product, restaurantId, restaurantName, extras = []) {
        let cart = this.get();

        // 1. Calcular o preço total dos extras (Garantindo que são números)
        const precoAdicionais = extras.reduce((sum, item) => sum + parseFloat(item.preco || 0), 0);
        
        // 2. Definir o preço final unitário (Base + Adicionais)
        const precoFinalUnitario = parseFloat(product.preco) + precoAdicionais;

        // 3. Criar uma chave única para a combinação (ID + Nomes dos Extras ordenados)
        // Isso garante que um lanche "Com Bacon" seja um item diferente de um "Sem Bacon"
        const extrasKey = extras.map(e => e.nome).sort().join('|');
        const uniqueId = extrasKey ? `${product.id}-${extrasKey}` : product.id;

        // 4. Verificar se já existe esse item EXATO no carrinho
        const existing = cart.items.find(i => i.uniqueId === uniqueId);

        if (existing) { 
            existing.quantity = Math.min(99, existing.quantity + 1); 
        } else { 
            cart.items.push({ 
                uniqueId: uniqueId, // Chave para diferenciar combinações
                product_id: product.id, 
                nome: product.nome, 
                preco: precoFinalUnitario, // Preço já computado (Base + Extras)
                image_url: product.image_url || product.imagem_url, 
                quantity: 1,
                restaurante_id: restaurantId,
                restaurante_nome: restaurantName,
                extras: extras // Guardamos a lista para exibir no checkout e dashboard
            }); 
        }
        
        this.save(cart);
        if (typeof showToast === 'function') {
            showToast(`${product.nome} adicionado ao carrinho!`);
        }
    },
    
    /**
     * Atualiza a quantidade usando o uniqueId para não confundir itens com extras diferentes.
     */
    updateQuantity(uniqueId, qty) {
        const cart = this.get();
        const item = cart.items.find(i => i.uniqueId === uniqueId);
        if (item) { 
            item.quantity = Math.max(1, Math.min(99, qty)); 
        }
        this.save(cart);
    },
    
    /**
     * Remove o item usando o uniqueId.
     */
    remove(uniqueId) {
        const cart = this.get();
        cart.items = cart.items.filter(i => i.uniqueId !== uniqueId);
        this.save(cart);
    },
    
    clear() { this.save({ items: [] }); },
    
    getTotal() { 
        const cart = this.get(); 
        return cart.items.reduce((t, i) => t + (parseFloat(i.preco) * i.quantity), 0); 
    },
    
    getTotalByRestaurant(restaurantId) { 
        const cart = this.get(); 
        return cart.items
            .filter(i => (i.restaurante_id || i.restaurant_id) === restaurantId)
            .reduce((t, i) => t + (parseFloat(i.preco) * i.quantity), 0); 
    },
    
    getCount() { 
        const cart = this.get(); 
        return cart.items.reduce((t, i) => t + i.quantity, 0); 
    },
    
    getRestaurants() { 
        const cart = this.get();
        const rests = {};
        cart.items.forEach(i => {
            const rId = i.restaurante_id || i.restaurant_id;
            const rNome = i.restaurante_nome || i.restaurant_nome;
            if (!rests[rId]) rests[rId] = { id: rId, nome: rNome, items: [] };
            rests[rId].items.push(i);
        });
        return Object.values(rests);
    },
    
    updateBadge() {
        const badge = document.getElementById('cart-badge');
        const count = this.getCount();
        if (badge) { 
            badge.textContent = count; 
            badge.classList.toggle('hidden', count === 0); 
        }
    }
};

// Vincula ao window para garantir compatibilidade com scripts inline
window.Cart = Cart;