import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { adminUsersApiService } from '@/lib/apis/admin-users-api.service';

export const ImpersonationBanner = () => {
  const router = useRouter();
  const [timeLeft, setTimeLeft] = useState<number>(900); // 15m default
  // Ideally this component reads from context/state to know if impersonation is active

  useEffect(() => {
    const handleEsc = async (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        await handleExit();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, []);

  const handleExit = async () => {
    try {
      await adminUsersApiService.exitImpersonation();
      router.push('/admin/users');
    } catch (e) {
      console.error(e);
    }
  };

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999]">
      <div className="fixed inset-0 border-4 border-amber-500/80 pointer-events-none" />
      <div className="fixed top-0 left-0 right-0 h-10 bg-amber-500 flex items-center justify-between px-4 pointer-events-auto shadow-md">
        <span className="text-black font-semibold">
          ⚠️ IMPERSONATION ACTIVE: Impersonating User | Session: {minutes}:{seconds.toString().padStart(2, '0')} remaining
        </span>
        <button
          onClick={handleExit}
          className="bg-black text-white px-3 py-1 rounded text-sm hover:bg-gray-800"
        >
          1-Click Exit Impersonation (Esc)
        </button>
      </div>
    </div>
  );
};
