import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {describe, it, expect, vi} from 'vitest';
vi.mock('./authApi',()=>({matrixSignIn:vi.fn()}));
import {matrixSignIn} from './authApi';
import {SignIn} from './SignIn';

describe('real Matrix sign-in screen with mocked transport (no network)',()=>{
  it('submits credentials and clears password after success',async()=>{
    matrixSignIn.mockResolvedValue({userId:'@alice:local'});
    const success=vi.fn();
    render(<SignIn onSignedIn={success}/>);
    fireEvent.change(screen.getByLabelText('Matrix user ID'),{target:{value:'@alice:local'}});
    fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-secret'}});
    fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
    await waitFor(()=>expect(success).toHaveBeenCalledTimes(1));
    expect(matrixSignIn).toHaveBeenCalledWith('@alice:local','test-secret');
    expect(screen.getByLabelText('Password')).toHaveValue('');
    expect(screen.queryByText(/fictional/i)).toBeNull();
  });
  it('does not authenticate on failed password',async()=>{
    matrixSignIn.mockRejectedValue(new Error('Matrix rejected the username or password.'));
    const success=vi.fn();
    render(<SignIn onSignedIn={success}/>);
    fireEvent.change(screen.getByLabelText('Matrix user ID'),{target:{value:'@bob:local'}});
    fireEvent.change(screen.getByLabelText('Password'),{target:{value:'wrong'}});
    fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
    await screen.findByRole('alert');
    expect(success).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Password')).toHaveValue('');
  });
});
