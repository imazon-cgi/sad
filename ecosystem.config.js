module.exports = {
  apps: [
    {
      name: "sad", // nome que aparecerá no PM2
      script: "server.js", // arquivo que inicia o servidor
      cwd: "C:/dashboards/imazon_dashboards", // diretório de trabalho
      instances: 1, // pode mudar para "max" se quiser usar todos os cores
      exec_mode: "fork", // ou "cluster" se quiser paralelizar
      watch: false, // desabilitado para não reiniciar a cada alteração
      env: {
        PORT: 3000, // porta do servidor
        NODE_ENV: "production"
      },
      error_file: "C:/dashboards/SAD/logs/pm2-error.log",
      out_file: "C:/dashboards/SAD/logs/pm2-out.log",
      time: true // adiciona timestamp nos logs
    }
  ]
};
