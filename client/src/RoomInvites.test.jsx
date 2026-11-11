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

it('enables new-session invitations when the previous join returns late',async()=>{
  let finishJoin;
  const old={invites:vi.fn().mockResolvedValue([{room:'!old:local',name:'Old invite'}]),
    joinRoom:vi.fn(()=>new Promise(resolve=>{finishJoin=resolve;}))};
  const next={invites:vi.fn().mockResolvedValue([{room:'!fresh:local',name:'New invite'}]),
    joinRoom:vi.fn().mockResolvedValue({room:'!fresh:local',joined:true})};
  const joined=vi.fn();
  const view=render(<RoomInvites api={old} onJoined={joined}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Join invitation Old invite'}));
  await waitFor(()=>expect(finishJoin).toBeTypeOf('function'));
  view.rerender(<RoomInvites api={next} onJoined={joined}/>);
  const fresh=await screen.findByRole('button',{name:'Join invitation New invite'});
  expect(fresh).toBeEnabled();
  expect(screen.getByRole('button',{name:'Refresh invitations'})).toBeEnabled();
  await act(async()=>finishJoin({room:'!old:local',joined:true}));
  expect(fresh).toBeEnabled();expect(joined).not.toHaveBeenCalled();
});

it('discovers a new Matrix invitation without requiring the invitee to click refresh',async()=>{
  vi.useFakeTimers();
  let view;
  try {
    const api={invites:vi.fn().mockResolvedValueOnce([])
      .mockResolvedValue([{room:'!new:local',name:'Late invitation'}]),joinRoom:vi.fn()};
    view=render(<RoomInvites api={api} onJoined={vi.fn()}/>);
    await act(async()=>{await Promise.resolve();});
    expect(screen.queryByRole('button',{name:'Join invitation Late invitation'})).toBeNull();
    await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});
    expect(screen.getByRole('button',{name:'Join invitation Late invitation'})).toBeInTheDocument();
    expect(api.invites).toHaveBeenCalledTimes(2);
  } finally {
    view?.unmount();
    vi.useRealTimers();
  }
});

it('keeps a pending Matrix join valid across background invitation polling',async()=>{
  vi.useFakeTimers();
  let finishJoin,view;
  try {
    const api={invites:vi.fn().mockResolvedValue([{room:'!pending:local',name:'Work group'}]),
      joinRoom:vi.fn(()=>new Promise(resolve=>{finishJoin=resolve;}))};
    const onJoined=vi.fn();
    view=render(<RoomInvites api={api} onJoined={onJoined}/>);
    await act(async()=>{await Promise.resolve();});
    fireEvent.click(screen.getByRole('button',{name:'Join invitation Work group'}));
    expect(finishJoin).toBeTypeOf('function');
    await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});
    expect(api.invites).toHaveBeenCalledTimes(2);
    await act(async()=>{finishJoin({room:'!pending:local',joined:true});await Promise.resolve();});
    expect(onJoined).toHaveBeenCalledExactlyOnceWith('!pending:local');
    expect(screen.queryByRole('button',{name:'Join invitation Work group'})).toBeNull();
  } finally {view?.unmount();vi.useRealTimers();}
});

it('preserves a Matrix join denial and pending invitations across a failed silent refresh',async()=>{
  vi.useFakeTimers();
  let view;
  try {
    const api={invites:vi.fn().mockResolvedValueOnce([{room:'!invite:local',name:'Team'}])
      .mockRejectedValueOnce(new Error('Matrix temporarily offline'))
      .mockResolvedValue([{room:'!invite:local',name:'Team'}]),
      joinRoom:vi.fn().mockRejectedValue(new Error('Not authorized to join'))};
    view=render(<RoomInvites api={api} onJoined={vi.fn()}/>);
    await act(async()=>{await Promise.resolve();});
    fireEvent.click(screen.getByRole('button',{name:'Join invitation Team'}));
    await act(async()=>{await Promise.resolve();});
    expect(screen.getByText('Not authorized to join')).toBeInTheDocument();
    await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});
    expect(screen.getByText('Matrix temporarily offline')).toBeInTheDocument();
    expect(screen.getByText('Not authorized to join')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Join invitation Team'})).toBeEnabled();
    await act(async()=>{await vi.advanceTimersByTimeAsync(10000);});
    expect(screen.queryByText('Matrix temporarily offline')).toBeNull();
    expect(screen.getByText('Not authorized to join')).toBeInTheDocument();
  } finally {view?.unmount();vi.useRealTimers();}
});
