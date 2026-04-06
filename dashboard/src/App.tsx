import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { ProductionTab } from "@/components/production/ProductionTab"
import { ConfigTab } from "@/components/config/ConfigTab"
import { ArchivesTab } from "@/components/archives/ArchivesTab"

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <h1
          className="text-2xl tracking-tight"
          style={{ fontFamily: "'Instrument Serif', serif" }}
        >
          IA qu'a demander
        </h1>
        <p className="text-sm text-muted-foreground">
          Pipeline editorial — tableau de bord
        </p>
      </header>

      <main className="flex-1 p-6">
        <Tabs defaultValue="production" className="w-full">
          <TabsList>
            <TabsTrigger value="production">Production</TabsTrigger>
            <TabsTrigger value="config">Config</TabsTrigger>
            <TabsTrigger value="archives">Archives</TabsTrigger>
          </TabsList>

          <TabsContent value="production" className="mt-4">
            <ProductionTab />
          </TabsContent>

          <TabsContent value="config" className="mt-4">
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
