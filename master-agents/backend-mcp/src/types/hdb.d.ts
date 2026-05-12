declare module 'hdb' {
  export interface ClientConfig {
    host: string;
    port: number;
    user: string;
    password: string;
  }

  export interface Client {
    connect(callback: (err: Error | null) => void): void;
    disconnect(callback: () => void): void;
    exec(sql: string, params: any[], callback: (err: Error | null, rows: any) => void): void;
  }

  export function createClient(config: ClientConfig): Client;
}
