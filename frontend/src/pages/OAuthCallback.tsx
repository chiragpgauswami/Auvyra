import { Loader2 } from "lucide-react";
import React, { useEffect, useRef } from "react";
import toast from "react-hot-toast";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const OAuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { handleOAuthCallback } = useAuth();
  const navigate = useNavigate();
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");
    const error = searchParams.get("error");

    if (error) {
      toast.error(`Authentication failed: ${decodeURIComponent(error)}`);
      navigate("/login", { replace: true });
      return;
    }

    if (!accessToken || !refreshToken) {
      toast.error("Missing authentication tokens in callback");
      navigate("/login", { replace: true });
      return;
    }

    handleOAuthCallback(accessToken, refreshToken)
      .then((user) => {
        toast.success(`Welcome back, ${user.name || "Creator"}!`);
        navigate("/channels", { replace: true });
      })
      .catch((err) => {
        console.error("OAuth token verification failed", err);
        toast.error("Failed to complete Google login");
        navigate("/login", { replace: true });
      });
  }, [searchParams, handleOAuthCallback, navigate]);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 max-w-md w-full text-center shadow-2xl">
        <Loader2 className="w-12 h-12 text-primary-500 animate-spin mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">
          Connecting Your Google Account
        </h2>
        <p className="text-slate-400 text-sm">
          Completing authentication and linking your YouTube channels...
        </p>
      </div>
    </div>
  );
};

export default OAuthCallback;
