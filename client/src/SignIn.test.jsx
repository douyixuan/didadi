import React from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {describe, it, expect, vi} from 'vitest';
vi.mock('./authApi',()=>({matrixSignIn:vi.fn()}));
import {matrixSignIn} from './authApi';
import {SignIn} from './SignIn';
import {App} from './App';

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
  it('keeps the successful login and exposes a retry when workspace startup is down',async()=>{
    const unauthenticated=Object.assign(new Error('Sign in to your Matrix account.'),{status:401});
    const connector=vi.fn().mockRejectedValueOnce(unauthenticated)
      .mockRejectedValueOnce(new Error('Matrix room listing unavailable'));
    matrixSignIn.mockResolvedValue({userId:'@alice:local'});
    render(<App connector={connector}/>);
    await screen.findByRole('main',{name:'Matrix sign in'});
    fireEvent.change(screen.getByLabelText('Matrix user ID'),{target:{value:'@alice:local'}});
    fireEvent.change(screen.getByLabelText('Password'),{target:{value:'secret'}});
    fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
    await screen.findByText('Matrix room listing unavailable');
    expect(screen.queryByRole('main',{name:'Matrix sign in'})).not.toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Retry connection'})).toBeInTheDocument();
    expect(connector).toHaveBeenCalledTimes(2);
    expect(matrixSignIn).toHaveBeenCalledTimes(1);
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
