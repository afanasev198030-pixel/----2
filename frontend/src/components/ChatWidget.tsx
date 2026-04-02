import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box, Fab, Dialog, IconButton, Typography, TextField, Stack,
  CircularProgress, Slide, useTheme, useMediaQuery, Avatar,
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const C = {
  accent: '#2563eb',
  accentDark: '#1d4ed8',
  bgUser: '#eef2ff',
  bgBot: '#ffffff',
  border: '#e2e8f0',
  textMuted: '#94a3b8',
};

export default function ChatWidget() {
  const { user } = useAuth();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `web_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 200);
    }
  }, [open]);

  if (!user) return null;

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const resp = await client.post('/ai/chat', {
        user_id: user.id,
        message: text,
        session_id: sessionId,
      });
      const botMsg: ChatMessage = {
        role: 'assistant',
        content: resp.data.response || 'Нет ответа.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '❌ Ошибка связи с AI. Попробуйте позже.', timestamp: new Date() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const chatContent = (
    <Box sx={{
      display: 'flex', flexDirection: 'column',
      height: isMobile ? '100vh' : 520,
      width: isMobile ? '100%' : 400,
      background: '#f8fafc',
    }}>
      {/* Header */}
      <Box sx={{
        px: 2, py: 1.5,
        background: C.accent,
        color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderRadius: isMobile ? 0 : '12px 12px 0 0',
      }}>
        <Stack direction="row" alignItems="center" spacing={1.5}>
          <SmartToyIcon sx={{ fontSize: 24 }} />
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: 15, lineHeight: 1.2 }}>AI-ассистент</Typography>
            <Typography sx={{ fontSize: 11, opacity: 0.8 }}>Digital Broker</Typography>
          </Box>
        </Stack>
        <IconButton size="small" onClick={() => setOpen(false)} sx={{ color: '#fff' }}>
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Messages */}
      <Box sx={{
        flex: 1, overflow: 'auto', px: 2, py: 1.5,
        display: 'flex', flexDirection: 'column', gap: 1.5,
      }}>
        {messages.length === 0 && (
          <Box sx={{ textAlign: 'center', mt: 4, color: C.textMuted }}>
            <SmartToyIcon sx={{ fontSize: 48, mb: 1, opacity: 0.3 }} />
            <Typography sx={{ fontSize: 14, mb: 0.5 }}>Привет! Я AI-ассистент Digital Broker.</Typography>
            <Typography sx={{ fontSize: 13, color: C.textMuted }}>
              Спросите меня о декларациях, кодах ТН ВЭД,
              правилах заполнения или статусе ваших документов.
            </Typography>
          </Box>
        )}
        {messages.map((msg, i) => (
          <Stack
            key={i}
            direction="row"
            spacing={1}
            alignItems="flex-start"
            sx={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}
          >
            {msg.role === 'assistant' && (
              <Avatar sx={{ width: 28, height: 28, bgcolor: C.accent, mt: 0.5 }}>
                <SmartToyIcon sx={{ fontSize: 16 }} />
              </Avatar>
            )}
            <Box sx={{
              px: 1.5, py: 1,
              borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
              background: msg.role === 'user' ? C.accent : C.bgBot,
              color: msg.role === 'user' ? '#fff' : '#0f172a',
              border: msg.role === 'assistant' ? `1px solid ${C.border}` : 'none',
              fontSize: 14,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.content}
            </Box>
            {msg.role === 'user' && (
              <Avatar sx={{ width: 28, height: 28, bgcolor: '#e2e8f0', mt: 0.5 }}>
                <PersonIcon sx={{ fontSize: 16, color: '#64748b' }} />
              </Avatar>
            )}
          </Stack>
        ))}
        {loading && (
          <Stack direction="row" spacing={1} alignItems="center" sx={{ alignSelf: 'flex-start' }}>
            <Avatar sx={{ width: 28, height: 28, bgcolor: C.accent }}>
              <SmartToyIcon sx={{ fontSize: 16 }} />
            </Avatar>
            <Box sx={{
              px: 2, py: 1, borderRadius: '12px', background: C.bgBot,
              border: `1px solid ${C.border}`,
            }}>
              <CircularProgress size={16} sx={{ color: C.accent }} />
            </Box>
          </Stack>
        )}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input */}
      <Box sx={{
        px: 2, py: 1.5,
        borderTop: `1px solid ${C.border}`,
        background: '#fff',
        borderRadius: isMobile ? 0 : '0 0 12px 12px',
      }}>
        <Stack direction="row" spacing={1} alignItems="flex-end">
          <TextField
            inputRef={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Задайте вопрос..."
            multiline
            maxRows={3}
            fullWidth
            size="small"
            disabled={loading}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: '10px',
                fontSize: 14,
                '& fieldset': { borderColor: C.border },
                '&:hover fieldset': { borderColor: C.accent },
                '&.Mui-focused fieldset': { borderColor: C.accent },
              },
            }}
          />
          <IconButton
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            sx={{
              bgcolor: C.accent, color: '#fff', width: 36, height: 36,
              '&:hover': { bgcolor: C.accentDark },
              '&.Mui-disabled': { bgcolor: '#e2e8f0', color: '#94a3b8' },
            }}
          >
            <SendIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Stack>
      </Box>
    </Box>
  );

  return (
    <>
      {/* FAB */}
      <Fab
        onClick={() => setOpen(true)}
        sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 1200,
          bgcolor: C.accent,
          color: '#fff',
          width: 56,
          height: 56,
          boxShadow: '0 4px 20px rgba(37,99,235,0.35)',
          '&:hover': { bgcolor: C.accentDark },
          display: open ? 'none' : 'flex',
        }}
      >
        <ChatIcon />
      </Fab>

      {/* Chat window */}
      {isMobile ? (
        <Dialog
          fullScreen
          open={open}
          onClose={() => setOpen(false)}
          TransitionComponent={Slide as any}
          TransitionProps={{ direction: 'up' } as any}
        >
          {chatContent}
        </Dialog>
      ) : (
        <Box sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 1300,
          borderRadius: '12px',
          overflow: 'hidden',
          boxShadow: '0 8px 40px rgba(0,0,0,0.15)',
          display: open ? 'block' : 'none',
        }}>
          {chatContent}
        </Box>
      )}
    </>
  );
}
