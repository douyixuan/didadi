import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {it,expect,vi} from 'vitest';
import {RoomInvites} from './RoomInvites';

it('lists current-user Matrix invitations but never joins or displays a room until confirmed',async()=>{
  const api={invites:vi.fn().mockResolvedValueOnce([{room:'!invite:local',name:'Team DM'}]).mockResolvedValue([]),
    joinRoom:vi.fn().mockResolvedValue({room:'!invite:local',joined:true})};
  const joined=vi.fn();
  render(<RoomInvites api={api} onJoined={joined}/>);
  const button=await screen.findByRole('button',{name:'Join invitation Team DM'});
  expect(joined).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(()=>expect(joined).toHaveBeenCalledWith('!invite:local'));
  expect(api.joinRoom).toHaveBeenCalledExactlyOnceWith('!invite:local');
  expect(screen.queryByRole('button',{name:'Join invitation Team DM'})).toBeNull();
});
it('retains a denied invitation without revealing a joined room',async()=>{
  const api={invites:vi.fn().mockResolvedValue([{room:'!private:local',name:'Private room'}]),
    joinRoom:vi.fn().mockRejectedValue(new Error('No current Matrix invitation'))};
  const joined=vi.fn();
  render(<RoomInvites api={api} onJoined={joined}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Join invitation Private room'}));
  await screen.findByText('No current Matrix invitation');
  expect(joined).not.toHaveBeenCalled();
  expect(screen.getByRole('button',{name:'Join invitation Private room'})).toBeEnabled();
});

it('discards late invitations from a previous authenticated account',async()=>{
  let resolveFirst;
  const oldApi={invites:vi.fn(()=>new Promise(resolve=>{resolveFirst=resolve;})),joinRoom:vi.fn()};
  const newApi={invites:vi.fn().mockResolvedValue([{room:'!new:local',name:'New account room'}]),joinRoom:vi.fn()};
  const joined=vi.fn();
  const view=render(<RoomInvites api={oldApi} onJoined={joined}/>);
  await waitFor(()=>expect(resolveFirst).toBeTypeOf('function'));
  view.rerender(<RoomInvites api={newApi} onJoined={joined}/>);
  await screen.findByRole('button',{name:'Join invitation New account room'});
  await act(async()=>resolveFirst([{room:'!old:local',name:'Former account secret'}]));
  expect(screen.queryByText('Former account secret')).toBeNull();
  expect(screen.getByText('New account room')).toBeInTheDocument();
  expect(joined).not.toHaveBeenCalled();
});
