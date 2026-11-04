// The password goes directly to the same-origin, loopback Matrix session adapter.
// Tokens stay on the server in an HttpOnly session; never use localStorage for auth.
export async function matrixSignIn(username, password, fetchFn = fetch) {
  const response = await fetchFn('/api/auth/login', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-Didadi-Login': '1'},
    body: JSON.stringify({username, password}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || 'Matrix sign-in failed. Try again.');
    error.status = response.status;
    throw error;
  }
  if (!data.userId || typeof data.userId !== 'string') {
    throw new Error('The server did not confirm your Matrix identity.');
  }
  return data;
}
