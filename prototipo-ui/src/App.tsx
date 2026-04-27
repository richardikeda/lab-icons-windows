import {
  Folder,
  FolderOpen,
  Image as ImageIcon,
  Monitor,
  Search,
  Settings,
  X,
  ArrowRight,
  Save,
  CheckCircle2,
  Trash2,
  RefreshCw,
  FolderPlus,
  Plus,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// Mock Data
type Target = {
  id: string;
  name: string;
  type: "shortcut" | "folder";
  theme: string;
  group: string;
  status: "mapped" | "customized" | "none";
  path: string;
  iconSrc?: string;
  originalIconSrc?: string;
};

const TARGETS: Target[] = [
  { id: "1", name: "personal", type: "folder", theme: "Sem grupo", group: "folders", status: "customized", path: "C:\\Users\\User\\Desktop\\personal", iconSrc: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=150&h=150&auto=format&fit=crop", originalIconSrc: "https://upload.wikimedia.org/wikipedia/commons/4/44/Folder_Icon.png" },
  { id: "2", name: "company", type: "folder", theme: "company", group: "folders", status: "customized", path: "C:\\Users\\User\\Desktop\\company" },
  { id: "3", name: "labs", type: "folder", theme: "laboratorio", group: "folders", status: "customized", path: "C:\\Users\\User\\Desktop\\labs" },
  { id: "4", name: "Music", type: "folder", theme: "music", group: "folders", status: "mapped", path: "C:\\Users\\User\\Music" },
  { id: "5", name: "Workspace", type: "folder", theme: "workspace", group: "folders", status: "mapped", path: "C:\\Users\\User\\Workspace" },
  { id: "6", name: "Spotify", type: "shortcut", theme: "Media", group: "apps", status: "none", path: "D:\\Workspace\\labs\\lab-icons-windows\\config\\managed-shortcuts\\Spotify.lnk", originalIconSrc: "https://upload.wikimedia.org/wikipedia/commons/1/19/Spotify_logo_without_text.svg" },
  { id: "7", name: "VS Code", type: "shortcut", theme: "Dev", group: "apps", status: "mapped", path: "C:\\Program Files\\Microsoft VS Code\\Code.exe" },
];

const ICONS = [
  { id: "spotify", name: "spotify pronto", src: "https://images.unsplash.com/photo-1614680376593-902f74a10dfa?q=80&w=150&h=150&auto=format&fit=crop" },
  { id: "whatsapp1", name: "whatsapp2 pronto", src: "https://images.unsplash.com/photo-1614680376408-81e91ffe3db7?q=80&w=150&h=150&auto=format&fit=crop" },
  { id: "whatsapp2", name: "whatsapp pronto", src: "https://images.unsplash.com/photo-1614680376739-414fae5479ea?q=80&w=150&h=150&auto=format&fit=crop" },
  { id: "vscode", name: "vscode pronto", src: "https://images.unsplash.com/photo-1614680376593-902f74a10dfa?q=80&w=150&h=150&auto=format&fit=crop" },
  { id: "music", name: "music pronto", src: "https://images.unsplash.com/photo-1510289982149-a2e6f47dfa19?q=80&w=150&h=150&auto=format&fit=crop" },
  { id: "labs", name: "labs novo", src: "https://images.unsplash.com/photo-1532094349884-543bc11b234d?q=80&w=150&h=150&auto=format&fit=crop" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("customized");
  const [selectedTargetId, setSelectedTargetId] = useState<string>("6");
  const [selectedIconId, setSelectedIconId] = useState<string | null>("spotify");
  const [searchIcon, setSearchIcon] = useState("");

  const selectedTarget = TARGETS.find((t) => t.id === selectedTargetId);
  const selectedIcon = ICONS.find((i) => i.id === selectedIconId);

  return (
    <TooltipProvider>
      <div className="flex h-screen w-full bg-slate-900 text-white overflow-hidden relative sm:p-8 font-sans selection:bg-blue-500/30">
        
        {/* Background Mesh Gradients */}
        <div className="absolute top-[-10%] left-[-10%] w-[60%] h-[60%] bg-blue-600/20 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-indigo-500/20 blur-[120px] rounded-full pointer-events-none"></div>

        {/* Main App Window */}
        <div className="w-full h-full bg-white/10 backdrop-blur-3xl border border-white/20 sm:rounded-3xl shadow-2xl flex overflow-hidden relative z-10">
        
        {/* LEFT SIDEBAR: Destinations */}
        <aside className="w-80 flex flex-col border-r border-white/10 shrink-0">
          <div className="p-4 pt-6 flex flex-col gap-4">
            <div>
              <h1 className="text-xl font-medium tracking-tight text-white flex items-center gap-2">
                <BoxIcon className="w-5 h-5 text-blue-400" />
                Lab Icons
              </h1>
              <p className="text-xs text-white/50 mt-1">Gerencie ícones de atalhos e pastas</p>
            </div>

            <div className="flex flex-col gap-2">
              <Button variant="secondary" className="w-full justify-start px-3 text-xs h-8 bg-white/5 hover:bg-white/10 border border-white/10 text-white/70">
                <Plus className="w-4 h-4 mr-2" /> Adicionar App
              </Button>
              <Button variant="secondary" className="w-full justify-start px-3 text-xs h-8 bg-white/5 hover:bg-white/10 border border-white/10 text-white/70">
                <FolderPlus className="w-4 h-4 mr-2" /> Adicionar Pasta
              </Button>
            </div>
            
            <Tabs defaultValue="customized" className="w-full" onValueChange={setActiveTab}>
              <TabsList className="w-full grid grid-cols-2 h-9 bg-black/20 border border-white/10 rounded-xl p-1">
                <TabsTrigger value="customized" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">Customizados</TabsTrigger>
                <TabsTrigger value="detected" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">Detectados</TabsTrigger>
              </TabsList>
            </Tabs>
            
            <div className="flex gap-1 overflow-auto no-scrollbar pb-1">
               <Badge variant="secondary" className="bg-blue-500/20 text-blue-300 hover:bg-blue-500/30 border border-blue-500/20 text-[10px] cursor-pointer">Todos</Badge>
               <Badge variant="outline" className="text-white/60 hover:text-white/80 border-white/10 bg-white/5 hover:bg-white/10 text-[10px] cursor-pointer">Atalhos</Badge>
               <Badge variant="outline" className="text-white/60 hover:text-white/80 border-white/10 bg-white/5 hover:bg-white/10 text-[10px] cursor-pointer">Pastas</Badge>
               <Badge variant="outline" className="text-white/60 hover:text-white/80 border-white/10 bg-white/5 hover:bg-white/10 text-[10px] cursor-pointer">Temas <ArrowRight className="w-3 h-3 ml-1" /></Badge>
            </div>
          </div>

          <Separator className="bg-white/10" />
          
          <ScrollArea className="flex-1">
            <div className="p-3 flex flex-col gap-1">
              {TARGETS.map((target) => (
                <div key={target.id} className="mb-2 last:mb-0">
                  <div className="text-[10px] uppercase font-semibold tracking-wider text-white/40 mb-1 px-2">{target.theme}</div>
                  <div
                    onClick={() => setSelectedTargetId(target.id)}
                    className={`flex items-center gap-3 p-2 rounded-xl cursor-pointer transition-all ${
                      selectedTargetId === target.id ? "bg-white/10 border border-white/20 shadow-lg" : "hover:bg-white/5 border border-transparent"
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 overflow-hidden p-1.5 ${
                      target.status === 'customized' || target.status === 'mapped' ? 'bg-black/20' : 'bg-transparent'
                    }`}>
                      {target.iconSrc ? (
                        <img src={target.iconSrc} alt={target.name} className="w-full h-full object-contain drop-shadow-sm" />
                      ) : target.type === "folder" ? (
                        <Folder className="w-5 h-5 text-white/50" />
                      ) : (
                        <Monitor className="w-5 h-5 text-white/50" />
                      )}
                    </div>
                    <div className="flex flex-col overflow-hidden">
                      <span className="text-sm font-medium text-white/80 truncate">{target.name}</span>
                      <span className="text-xs text-white/40 truncate flex items-center gap-1">
                        {target.type === "folder" ? <FolderOpen className="w-3 h-3" /> : <Monitor className="w-3 h-3" />}
                        {target.status === 'customized' ? 'Customizado' : target.status === 'mapped' ? 'Mapeado' : 'Detectado'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </aside>

        {/* MAIN CENTER: Details & Preview */}
        <main className="flex-1 flex flex-col min-w-0">
          <header className="h-14 flex items-center justify-between px-6 border-b border-white/10">
            <div className="flex items-center gap-6">
              <div className="flex items-center space-x-2">
                <Switch id="auto-reapply" defaultChecked />
                <Label htmlFor="auto-reapply" className="text-xs text-white/60 cursor-pointer">Reaplicar no boot</Label>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="w-8 h-8 text-white/60 hover:text-white"><Settings className="w-4 h-4" /></Button>
            </div>
          </header>

          <ScrollArea className="flex-1">
            {selectedTarget ? (
              <div className="max-w-4xl mx-auto p-8 space-y-10">
                
                {/* Visual Preview Stage */}
                <section className="relative">
                  <div className="absolute inset-0 bg-gradient-to-b from-blue-500/10 to-transparent rounded-3xl pointer-events-none" />
                  <div className="flex items-center justify-center gap-12 p-12 py-16 border border-white/10 bg-black/20 rounded-3xl backdrop-blur-sm">
                    
                    {/* Original */}
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center shadow-inner overflow-hidden relative group">
                        {selectedTarget.originalIconSrc ? (
                           <img src={selectedTarget.originalIconSrc} className="w-12 h-12 object-contain opacity-70 group-hover:opacity-100 transition-opacity" alt="Original" />
                        ) : selectedTarget.type === 'folder' ? (
                          <Folder className="w-8 h-8 text-white/60" />
                        ) : (
                          <Monitor className="w-8 h-8 text-white/60" />
                        )}
                        <Badge className="absolute bottom-1 right-1 text-[8px] px-1 py-0 h-4 bg-black/40 text-white/60 border border-white/10">Orig.</Badge>
                      </div>
                      <span className="text-sm font-medium text-white/50">Original</span>
                    </div>

                    <ArrowRight className="w-8 h-8 text-white/20" strokeWidth={1} />

                    {/* New/Current */}
                    <div className="flex flex-col items-center gap-4 relative">
                      <div className="absolute -inset-4 bg-blue-500/20 blur-2xl rounded-full opacity-0 animate-in fade-in fill-mode-forwards delay-150 duration-1000 pointer-events-none" />
                      <div className="w-32 h-32 rounded-3xl border-2 border-blue-500 bg-white/10 backdrop-blur-md flex items-center justify-center shadow-[0_0_40px_rgba(59,130,246,0.3)] overflow-hidden relative z-10 transition-all duration-300 ring-4 ring-slate-900 p-4">
                         {selectedIcon ? (
                           <img src={selectedIcon.src} className="w-full h-full object-contain drop-shadow-xl" alt="New Icon" />
                         ) : selectedTarget.iconSrc ? (
                           <img src={selectedTarget.iconSrc} className="w-full h-full object-contain drop-shadow-xl" alt="Current Icon" />
                         ) : (
                           <ImageIcon className="w-10 h-10 text-white/30" />
                         )}
                         <div className="absolute inset-0 shadow-[inset_0_0_20px_rgba(0,0,0,0.5)] pointer-events-none rounded-3xl" />
                      </div>
                      <span className="text-sm font-medium text-white">
                        {selectedIcon ? "Novo ícone preparado" : "Ícone atual"}
                      </span>
                    </div>

                  </div>
                </section>

                {/* Form fields */}
                <section className="space-y-6">
                  <div className="grid grid-cols-12 gap-6 items-start">
                    
                    <div className="col-span-12 md:col-span-8 space-y-4">
                      <div className="space-y-1.5">
                        <Label className="text-xs text-white/50">Destino</Label>
                        <div className="flex gap-2">
                          <Input value={selectedTarget.path} readOnly className="bg-black/20 border-white/10 text-sm font-mono text-white/80 focus-visible:ring-blue-500 rounded-xl" />
                          <Button variant="secondary" className="bg-white/5 hover:bg-white/10 border border-white/10 text-white shrink-0 rounded-xl">Localizar</Button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <Label className="text-xs text-white/50">Nome</Label>
                          <Input defaultValue={selectedTarget.name} className="bg-black/20 border-white/10 text-sm rounded-xl text-white" />
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs text-white/50">Tema (Agrupamento)</Label>
                          <Input defaultValue={selectedTarget.theme} className="bg-black/20 border-white/10 text-sm rounded-xl text-white" />
                        </div>
                      </div>
                    </div>

                    <div className="col-span-12 md:col-span-4 space-y-4">
                      <Card className="bg-black/20 border-white/10 shadow-none rounded-2xl">
                        <CardContent className="p-4 space-y-4">
                           <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Tipo</Label>
                            <Tabs defaultValue={selectedTarget.type} className="w-full">
                              <TabsList className="w-full grid grid-cols-2 h-9 bg-black/40 border border-white/10 p-1 rounded-xl">
                                <TabsTrigger value="shortcut" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">Atalho .lnk</TabsTrigger>
                                <TabsTrigger value="folder" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">Pasta</TabsTrigger>
                              </TabsList>
                            </Tabs>
                          </div>
                          <div className="space-y-1.5">
                            <Label className="text-xs text-white/50">Asset preferido</Label>
                            <Tabs defaultValue="ico" className="w-full">
                              <TabsList className="w-full grid grid-cols-2 h-9 bg-black/40 border border-white/10 p-1 rounded-xl">
                                <TabsTrigger value="ico" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">ICO Multi-size</TabsTrigger>
                                <TabsTrigger value="png" className="text-xs data-[state=active]:bg-white/10 data-[state=active]:text-white text-white/50 rounded-lg">PNG Limpo</TabsTrigger>
                              </TabsList>
                            </Tabs>
                          </div>
                        </CardContent>
                      </Card>
                    </div>

                  </div>
                </section>

                {/* Primary Actions */}
                <section className="flex items-center gap-3 pt-4 border-t border-white/10">
                  <Button className="h-12 px-8 bg-blue-500 hover:bg-blue-600 rounded-xl text-white font-semibold shadow-lg shadow-blue-500/20 transition-all border-none">
                    <Save className="w-4 h-4 mr-2" /> Salvar e aplicar
                  </Button>
                  <Button variant="outline" className="h-12 border border-white/10 bg-white/5 hover:bg-white/10 text-white rounded-xl transition-all">
                    <RefreshCw className="w-4 h-4 mr-2" /> Verificar agora
                  </Button>
                  <div className="flex-1" />
                  {selectedTarget.status !== 'none' && (
                     <Button variant="ghost" className="h-12 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-xl">
                       <Trash2 className="w-4 h-4 mr-2" /> Remover customização
                     </Button>
                  )}
                </section>

              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-white/40">
                <BoxIcon className="w-16 h-16 mb-4 opacity-20" />
                <p>Selecione um destino ou adicione um novo.</p>
              </div>
            )}
          </ScrollArea>
        </main>

        {/* RIGHT SIDEBAR: Icon Library */}
        <aside className="w-80 flex flex-col border-l border-white/10 overflow-hidden shrink-0">
          <div className="p-4 flex flex-col gap-4 border-b border-white/10">
             <div className="space-y-1">
               <h2 className="text-sm font-medium text-white">Biblioteca Visual</h2>
               <p className="text-[10px] text-white/50">assets disponíveis em icons-in/</p>
             </div>
             
             <div className="relative">
               <Search className="w-4 h-4 absolute left-3 top-2.5 text-white/50" />
               <Input 
                 placeholder="Filtrar por nome..." 
                 className="pl-9 h-9 bg-black/20 border-white/10 text-xs text-white focus-visible:ring-blue-500 rounded-xl"
                 value={searchIcon}
                 onChange={(e) => setSearchIcon(e.target.value)}
               />
             </div>
          </div>

          <ScrollArea className="flex-1 p-4">
             <div className="grid grid-cols-3 gap-3">
               {ICONS.filter(i => i.name.toLowerCase().includes(searchIcon.toLowerCase())).map((icon) => (
                 <div
                   key={icon.id}
                   onClick={() => setSelectedIconId(icon.id)}
                   className={`group relative flex flex-col gap-2 cursor-pointer rounded-2xl p-2 transition-all ${
                     selectedIconId === icon.id 
                       ? "bg-white/10 ring-2 ring-blue-500 ring-offset-slate-900 ring-offset-2" 
                       : "hover:bg-white/10 bg-white/5 border border-white/10"
                   }`}
                 >
                   <div className="aspect-square rounded-xl overflow-hidden bg-black/20 flex items-center justify-center p-3">
                     <img src={icon.src} alt={icon.name} className="w-full h-full object-contain drop-shadow-md group-hover:scale-110 transition-transform duration-300" />
                   </div>
                   <span className="text-[10px] font-medium text-center text-white/60 truncate w-full px-1">
                     {icon.name}
                   </span>
                   {selectedIconId === icon.id && (
                     <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full border-2 border-slate-900" />
                   )}
                 </div>
               ))}
             </div>
          </ScrollArea>

          <div className="p-4 border-t border-white/10 space-y-2">
             <Button className="w-full text-xs h-10 bg-blue-500 hover:bg-blue-600 rounded-xl text-white shadow-lg shadow-blue-500/20 border-none transition-all">
               Processar pacote em background
             </Button>
             <Button variant="ghost" className="w-full text-xs h-10 text-white/60 hover:text-white hover:bg-white/10 rounded-xl">
               Abrir pasta icons-out
             </Button>
          </div>
        </aside>

        </div>
      </div>
    </TooltipProvider>
  );
}

function BoxIcon(props: React.ComponentProps<"svg">) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.29 7 12 12 20.71 7" />
      <line x1="12" y1="22" x2="12" y2="12" />
    </svg>
  );
}
