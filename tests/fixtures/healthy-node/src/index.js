exports.total = (items) => items.reduce((sum, i) => sum + i.price * i.qty, 0);
