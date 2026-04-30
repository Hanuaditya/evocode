import React from 'react';

function Checkout({ user, order }) {
  const userEmail = user?.email;

  return (
    <div className="checkout-container">
      <h2>Checkout Summary</h2>
      <p>Billing Email: {userEmail}</p>
      <p>Order Total: ${order ? order.total : 0}</p>
    </div>
  );
}

export default Checkout;