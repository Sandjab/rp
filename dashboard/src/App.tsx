import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { ProductionTab } from "@/components/production/ProductionTab"
import { ConfigTab } from "@/components/config/ConfigTab"
import { ArchivesTab } from "@/components/archives/ArchivesTab"

function App() {
  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1
          className="font-serif text-2xl tracking-tight"
        >
          IA qu'à demander
        </h1>
        <p className="text-sm text-muted-foreground">
          Pipeline éditorial — tableau de bord
        </p>
      </header>

      <main className="flex-1 min-h-0 flex flex-col">
        <Tabs defaultValue="production" className="flex-1 flex flex-col min-h-0">
          <TabsList>
            <TabsTrigger value="production">Production</TabsTrigger>
            <TabsTrigger value="config">Config</TabsTrigger>
            <TabsTrigger value="archives">Archives</TabsTrigger>
          </TabsList>

          <TabsContent value="production" className="flex-1 min-h-0 mt-4">
            <ProductionTab />
          </TabsContent>

          <TabsContent value="config" className="flex-1 flex flex-col min-h-0 mt-4">
            <ConfigTab />
          </TabsContent>

          <TabsContent value="archives" className="mt-4">
            <ArchivesTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

export default App
