import { render } from '@testing-library/react';
import React from 'react';
import Checkout from '../src/checkout';

describe('Checkout Component', () => {
  it('renders successfully when user is provided', () => {
    const mockUser = { email: 'test@example.com' };
    const { getByText } = render(<Checkout user={mockUser} order={{ total: 100 }} />);
    expect(getByText(/test@example.com/)).toBeTruthy();
  });

  it('handles null user safely without crashing', () => {
    // This test currently FAILS because the bug exists in Checkout
    // The component tries to access 'email' of null/undefined
    expect(() => {
      render(<Checkout user={null} order={{ total: 50 }} />);
    }).not.toThrow();
  });
});
