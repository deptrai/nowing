import React from 'react';

export default function AdminUsersPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Admin Hub: Users</h1>
      <div className="flex gap-4 mb-4">
        <div className="p-4 border rounded">Total users: 0</div>
        <div className="p-4 border rounded">Active workspaces: 0</div>
      </div>
      <div className="border rounded p-4 h-[500px]">
        {/* High-density data matrix layout */}
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left border-b p-2">User ID</th>
              <th className="text-left border-b p-2">Email</th>
              <th className="text-left border-b p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="p-2 border-b">123</td>
              <td className="p-2 border-b">user@example.com</td>
              <td className="p-2 border-b">
                <button className="text-blue-500 mr-2">Impersonate</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
